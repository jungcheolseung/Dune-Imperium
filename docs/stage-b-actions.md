# B단계 행동 분류표 (부록)

master `e7e9ad4f`(codec v149), 옵션 전부 + Leader draft 카탈로그. [stage-b-plan.md](stage-b-plan.md) 2절의 범위 결정(2026-10-19:
차례 행동의 대상도 두 단계, 수량은 그대로)을 행동마다 적용한 것이다. `box`·`source` 꼬리표 인자는 뺐다(결정 3의 이름표가 맡는다).
유닛 조합(`count`·`commanders`·`zone`)은 수량이라 한 행의 인자로 남는다. 진영 고르기의 `alliance_recipient`(동맹을 넘겨받을 좌석)는
필요할 때만 뒤따르는 단계로 연다.

| 행동 | 동사 | 출처 | 대상 | 행 | 인자 | B단계 처리 |
| --- | --- | --- | --- | ---: | --- | --- |
| `decline_acquisition_spy` | decline | acquisition | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `place_acquisition_spy` | place_spy | acquisition | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `recall_spy_for_acquisition` | recall_spy | acquisition | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `acquire_imperium_by_card` | acquire | agent_card | imperium_card | 270 | instance_id | 두 단계: 효과 → 대상 |
| `acquire_imperium_with_solari` | acquire | agent_card | imperium_card | 270 | instance_id | 두 단계: 효과 → 대상 |
| `acquire_reserve_by_card` | acquire | agent_card | reserve_card | 4 | card_id | 두 단계: 효과 → 대상 |
| `acquire_reserve_with_solari` | acquire | agent_card | reserve_card | 4 | card_id | 두 단계: 효과 → 대상 |
| `choose_agent_card_influence` | gain_influence | agent_card | faction | 8 | faction | 두 단계: 효과 → 대상 |
| `choose_agent_card_reward` | choose | agent_card | option | 8 | reward | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `complete_contract_by_card` | complete_contract | agent_card | contract | 56 | instance_id | 두 단계: 효과 → 대상 |
| `decline_agent_card_acquisition` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_agent_card_discard` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_agent_card_intrigue_payment` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_agent_card_payment` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_agent_card_recall` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_agent_card_spy` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_agent_card_trash` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_corrinth_city_payment` | decline | agent_card | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `discard_agent_card` | discard | agent_card | personal_card | 366 | card_id | 두 단계: 효과 → 대상 |
| `keep_peeked_intrigue` | keep | agent_card | intrigue_card | 89 | instance_id | 두 단계: 효과 → 대상 |
| `lose_agent_card_troop` | lose_unit | agent_card | units | 8 | commanders, zone | 한 단계(수량: 유닛 조합) |
| `pay_agent_card_five_solari_for_tleilaxu` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_agent_card_intrigue_and_spice` | pay | agent_card | intrigue_card | 178 | intrigue_card_id | 두 단계: 효과 → 대상 |
| `pay_agent_card_specimen` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_agent_card_spice` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_agent_card_spice_for_sandworm` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_agent_card_spice_for_sandworm_and_shield_wall` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_agent_card_two_specimens` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_agent_card_water` | pay | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `pay_corrinth_city` | pay | agent_card | personal_card | 366 | card_id | 두 단계: 효과 → 대상 |
| `place_agent_card_spy` | place_spy | agent_card | post | 26 | post_id | 두 단계: 효과 → 대상 |
| `recall_agent_for_agent_card` | recall_agent | agent_card | space | 46 | space_id | 두 단계: 효과 → 대상 |
| `recall_conflict_agent_for_agent_card` | recall_agent | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `recall_spy_for_agent_card` | recall_spy | agent_card | post | 26 | post_id | 두 단계: 효과 → 대상 |
| `resolve_agent_card_effect` | resolve | agent_card | option | 24 | effect | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `retreat_opponent_troop` | retreat | agent_card | units | 16 | commanders, player | 두 단계: 효과 → 대상 |
| `select_corrinth_city_discard` | discard | agent_card | personal_card | 366 | card_id | 두 단계: 효과 → 대상 |
| `select_long_live_fighters_discard` | discard | agent_card | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `select_long_live_fighters_draw` | draw | agent_card | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `take_agent_card_combat_icon` | gain | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `trash_agent_card` | trash | agent_card | personal_card | 366 | card_id | 두 단계: 효과 → 대상 |
| `trash_agent_card_self_for_vp` | trash | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `trash_grafted_card_for_influence` | trash | agent_card | personal_card | 366 | card_id | 두 단계: 효과 → 대상 |
| `trash_grafted_card_for_specimen` | trash | agent_card | none | 2 |  | 한 단계(대상 없음) |
| `trash_intrigue_for_agent_card` | trash | agent_card | intrigue_card | 178 | intrigue_card_id | 두 단계: 효과 → 대상 |
| `choose_shipping_influence` | gain_influence | board_space | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `harvest_maker_spice` | gain | board_space | space | 3 | space_id | 두 단계: 효과 → 대상 |
| `recall_agent_for_imperial_privilege` | recall_agent | board_space | space | 23 | space_id | 두 단계: 효과 → 대상 |
| `recall_conflict_agent_for_imperial_privilege` | recall_agent | board_space | none | 1 |  | 한 단계(대상 없음) |
| `recall_spy_for_espionage` | recall_spy | board_space | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `resolve_board_effect` | resolve | board_space | option | 8 | effect | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `resolve_espionage_place_spy` | place_spy | board_space | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `resolve_espionage_without_spy` | resolve_empty | board_space | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `resolve_faction_influence` | gain_influence | board_space | none | 1 |  | 한 단계(대상 없음) |
| `resolve_imperial_privilege_without_recall` | resolve_empty | board_space | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `summon_maker_sandworms` | summon_sandworm | board_space | space | 2 | space_id | 두 단계: 효과 → 대상 |
| `take_desert_riding_hooks` | take | board_space | space | 1 | space_id | 두 단계: 효과 → 대상 |
| `take_sietch_tabr_supplies` | choose | board_space | none | 1 |  | 한 단계(대상 없음) |
| `take_sietch_tabr_water` | choose | board_space | none | 1 |  | 한 단계(대상 없음) |
| `take_sietch_tabr_water_and_destroy_wall` | choose | board_space | none | 1 |  | 한 단계(대상 없음) |
| `take_tuek_sietch_card` | choose | board_space | none | 1 |  | 한 단계(대상 없음) |
| `take_tuek_sietch_spice` | choose | board_space | none | 1 |  | 한 단계(대상 없음) |
| `trash_card_for_desert_tactics` | trash | board_space | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `trash_intrigue_for_imperial_privilege` | trash | board_space | intrigue_card | 89 | card_id | 두 단계: 효과 → 대상 |
| `acquire_sardaukar_commander` | acquire | commander | skill | 8 | skill_id | 두 단계: 효과 → 대상 |
| `choose_skill` | choose | commander | skill | 7 | skill_id | 두 단계: 효과 → 대상 |
| `decline_skill` | decline | commander | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `recruit_sardaukar_commander` | recruit | commander | none | 1 |  | 한 단계(대상 없음) |
| `resolve_commander_without_skill` | resolve_empty | commander | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `trash_skill_for_strength` | trash | commander | skill | 7 | skill_id | 두 단계: 효과 → 대상 |
| `choose_combat_reward_influence` | gain_influence | conflict | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `choose_distinct_combat_reward_influence` | gain_influence | conflict | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `decline_combat_reward` | decline | conflict | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_combat_reward_spy` | decline | conflict | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_combat_reward_trash` | decline | conflict | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_control_defense` | decline | conflict | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `deploy_control_defense` | deploy | conflict | none | 1 |  | 한 단계(대상 없음) |
| `pay_combat_reward` | pay | conflict | none | 1 |  | 한 단계(대상 없음) |
| `place_combat_reward_spy` | place_spy | conflict | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `recall_spies_for_combat_reward` | recall_spy | conflict | post | 156 | first_post_id, second_post_id | 두 단계 + 순서: 회수 → 첫 초소 → 둘째 초소 |
| `recall_spy_for_combat_reward` | recall_spy | conflict | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `resolve_combat_influence_without_faction` | resolve_empty | conflict | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `resolve_combat_trash_without_card` | resolve_empty | conflict | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `trash_combat_reward_card` | trash | conflict | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `complete_contract` | complete_contract | contract | contract | 28 | instance_id | 두 단계: 효과 → 대상 |
| `decline_contract_spy` | decline | contract | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `hold_contract_icons` | resolve_empty | contract | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `place_contract_spy` | place_spy | contract | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `recall_agent_for_contract` | recall_agent | contract | space | 23 | space_id | 두 단계: 효과 → 대상 |
| `recall_conflict_agent_for_contract` | recall_agent | contract | none | 1 |  | 한 단계(대상 없음) |
| `recall_spy_for_contract` | recall_spy | contract | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `resolve_contract_icons_without_contract` | resolve_empty | contract | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `resolve_contract_without_recall` | resolve_empty | contract | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `take_contract` | take | contract | contract | 28 | instance_id | 두 단계: 효과 → 대상 |
| `trash_intrigue_for_contract` | trash | contract | intrigue_card | 89 | card_id | 두 단계: 효과 → 대상 |
| `match_endgame_wild_icon` | match | endgame | wild_icon | 60 | matching_card_id, wild_card_id | 두 단계 + 순서: 맞추기 → 카드 → 와일드 카드 |
| `place_track_spy` | place_spy | influence_track | none | 1 |  | 한 단계(대상 없음) |
| `acquire_intrigue_imperium` | acquire | intrigue | imperium_card | 135 | instance_id | 두 단계: 효과 → 대상 |
| `acquire_intrigue_reclaimed_forces` | acquire | intrigue | reclaimed_forces | 2 | choice | 두 단계: 효과 → 대상 |
| `acquire_intrigue_reserve` | acquire | intrigue | reserve_card | 2 | card_id | 두 단계: 효과 → 대상 |
| `acquire_intrigue_tleilaxu` | acquire | intrigue | tleilaxu_card | 38 | instance_id, to_deck_top | 두 단계: 획득 → 카드 (`to_deck_top`은 카드 행의 변형) |
| `choose_intrigue_discard` | discard | intrigue | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `choose_intrigue_faction` | gain_influence | intrigue | faction | 20 | alliance_recipient, faction | 두 단계: 효과 → 대상 |
| `decline_conflict_end_intrigue` | decline | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_intrigue_spy` | decline | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_intrigue_tleilaxu` | decline | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_intrigue_trash` | decline | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_spy_placement` | resolve_empty | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `deploy_intrigue_troops` | deploy | intrigue | units | 15 | commanders, count | 한 단계(수량: 유닛 조합) |
| `detonate_shield_wall` | destroy_shield_wall | intrigue | none | 1 |  | 한 단계(대상 없음) |
| `discard_top_card` | discard | intrigue | none | 1 |  | 한 단계(대상 없음) |
| `draw_top_card_for_solari` | draw | intrigue | none | 1 |  | 한 단계(대상 없음) |
| `finish_conflict_end_intrigue` | finish | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `finish_intrigue_effects` | finish | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `flip_battle_card` | flip | intrigue | conflict_card | 23 | card_id | 두 단계: 효과 → 대상 |
| `give_intrigue_card` | give | intrigue | intrigue_card | 356 | card_id, player | 두 단계 + 순서: 주기 → 카드 → 받는 좌석 |
| `keep_shield_wall` | decline | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `lose_intrigue_troop` | lose_unit | intrigue | units | 4 | commanders, zone | 한 단계(수량: 유닛 조합) |
| `manipulate_imperium_row` | set_aside | intrigue | imperium_card | 135 | instance_id | 두 단계: 효과 → 대상 |
| `place_intrigue_spy` | place_spy | intrigue | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `place_spy_on_space` | place_spy | intrigue | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `play_conflict_end_intrigue` | play | intrigue | intrigue_card | 2 | card_id | 두 단계: 효과 → 대상 |
| `play_intrigue` | play | intrigue | intrigue_card | 122 | card_id, option | 두 단계 + 갈래: 책략 내기 → 카드 → 갈래 |
| `put_back_top_card` | keep | intrigue | none | 1 |  | 한 단계(대상 없음) |
| `recall_spy_for_intrigue` | recall_spy | intrigue | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `recall_spy_for_placement` | recall_spy | intrigue | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `resolve_intrigue_influence_without_faction` | resolve_empty | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `resolve_intrigue_rewards` | resolve | intrigue | none | 1 |  | 한 단계(대상 없음) |
| `retreat_intrigue_troops` | retreat | intrigue | units | 104 | commanders, count | 한 단계(수량: 유닛 조합) |
| `skip_intrigue_acquisition` | resolve_empty | intrigue | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `take_trigger_contract` | take | intrigue | contract | 28 | instance_id | 두 단계: 효과 → 대상 |
| `trash_intrigue_card` | trash | intrigue | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `trash_intrigue_hand_card` | trash | intrigue | intrigue_card | 89 | card_id | 두 단계: 효과 → 대상 |
| `use_intrigue_effect` | use | intrigue | option | 2 | section | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `acquire_leader_imperium` | acquire | leader | imperium_card | 270 | instance_id | 두 단계: 효과 → 대상 |
| `acquire_leader_reserve` | acquire | leader | reserve_card | 4 | card_id | 두 단계: 효과 → 대상 |
| `advance_feyd_track` | advance | leader | track_space | 14 | space_id | 두 단계: 효과 → 대상 |
| `choose_leader_signet_influence` | gain_influence | leader | faction | 8 | faction | 두 단계: 효과 → 대상 |
| `choose_secret_project` | choose | leader | tech | 18 | tech_id | 두 단계: 효과 → 대상 |
| `decline_leader_card_trash` | decline | leader | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_leader_signet_payment` | decline | leader | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_leader_spy_placement` | decline | leader | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_navigation` | decline | leader | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_optional_trash` | decline | leader | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `deploy_leader_agent` | deploy | leader | none | 2 |  | 한 단계(대상 없음) |
| `draw_planetologist_intrigue` | draw | leader | none | 1 |  | 한 단계(대상 없음) |
| `gain_leader_signet_spice` | gain | leader | none | 2 |  | 한 단계(대상 없음) |
| `gain_leader_signet_troop` | recruit | leader | none | 2 |  | 한 단계(대상 없음) |
| `pay_leader_board_repeat` | pay | leader | none | 1 |  | 한 단계(대상 없음) |
| `pay_leader_signet_solari` | pay | leader | none | 2 |  | 한 단계(대상 없음) |
| `pay_leader_signet_spice` | pay | leader | none | 2 |  | 한 단계(대상 없음) |
| `pay_leader_signet_water` | pay | leader | none | 2 |  | 한 단계(대상 없음) |
| `place_leader_bonus_spice` | place_bonus | leader | none | 2 |  | 한 단계(대상 없음) |
| `place_leader_spy` | place_spy | leader | post | 26 | post_id | 두 단계: 효과 → 대상 |
| `place_navigation_card` | choose | leader | navigation_card | 10 | card_id | 두 단계: 효과 → 대상 |
| `play_navigation` | play | leader | option | 2 | option | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `recall_spy_for_leader` | recall_spy | leader | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `recall_spy_for_leader_placement` | recall_spy | leader | post | 26 | post_id | 두 단계: 효과 → 대상 |
| `resolve_leader_signet_without_option` | resolve_empty | leader | none | 2 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `retreat_leader_commander` | retreat | leader | none | 1 |  | 한 단계(대상 없음) |
| `retreat_leader_troop` | retreat | leader | none | 1 |  | 한 단계(대상 없음) |
| `retreat_leader_troops` | retreat | leader | units | 206 | commanders, count | 한 단계(수량: 유닛 조합) |
| `take_leader_bonus_spice` | take | leader | space | 8 | space_id | 두 단계: 효과 → 대상 |
| `trash_leader_card` | trash | leader | personal_card | 366 | card_id | 두 단계: 효과 → 대상 |
| `trash_leader_tech` | trash | leader | tech | 36 | tech_id | 두 단계: 효과 → 대상 |
| `trash_optional_card` | trash | leader | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `use_other_memories` | use | leader | none | 1 |  | 한 단계(대상 없음) |
| `discard_opponent_card` | discard | opponent | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `lose_moved_spy` | lose_spy | opponent | none | 1 |  | 한 단계(대상 없음) |
| `lose_unit` | lose_unit | opponent | units | 4 | commanders, zone | 한 단계(수량: 유닛 조합) |
| `move_spy` | move_spy | opponent | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `resolve_unit_loss_without_unit` | resolve_empty | opponent | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `acquire_imperium` | acquire | purchase | imperium_card | 135 | instance_id | 두 단계: 효과 → 대상 |
| `acquire_manipulated_imperium` | acquire | purchase | imperium_card | 135 | instance_id | 두 단계: 효과 → 대상 |
| `acquire_reclaimed_forces` | acquire | purchase | reclaimed_forces | 2 | choice | 두 단계: 효과 → 대상 |
| `acquire_reserve` | acquire | purchase | reserve_card | 2 | card_id | 두 단계: 효과 → 대상 |
| `acquire_tleilaxu` | acquire | purchase | tleilaxu_card | 38 | instance_id, to_deck_top | 두 단계: 획득 → 카드 (`to_deck_top`은 카드 행의 변형) |
| `choose_research_influence` | gain_influence | research | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `choose_research_space` | advance | research | track_space | 21 | space_id | 두 단계: 효과 → 대상 |
| `decline_research_bonus` | decline | research | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `pay_research_bonus` | pay | research | none | 1 |  | 한 단계(대상 없음) |
| `resolve_research_icon` | resolve | research | option | 5 | effect | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `trash_intrigue_for_research_bonus` | trash | research | intrigue_card | 89 | card_id | 두 단계: 효과 → 대상 |
| `advance_reveal_research` | advance | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `advance_reveal_tleilaxu` | advance | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `command_acquire_row_card` | acquire | reveal_card | imperium_card | 135 | instance_id | 두 단계: 효과 → 대상 |
| `decline_command_acquisition` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_card_trash` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_influence_exchange` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_influence_loss` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_sandworm` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_spice_influence` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_spy_recall` | decline | reveal_card | none | 5 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_troop_move` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_troop_retreat` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `decline_reveal_troop_sacrifice` | decline | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `defer_reveal_choice` | pass | reveal_card | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `deploy_reveal_card_troop` | deploy | reveal_card | units | 6 | commanders | 한 단계(수량: 유닛 조합) |
| `draw_reveal_intrigue` | draw | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `exchange_reveal_influence` | exchange_influence | reveal_card | faction | 80 | alliance_recipient, gained_faction, lost_faction | 두 단계 + 순서: 교환 → 잃을 진영 → 얻을 진영 |
| `gain_five_reveal_solari` | gain | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `gain_reveal_faction_influence` | gain_influence | reveal_card | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `gain_reveal_influence` | gain_influence | reveal_card | faction | 12 | faction | 두 단계: 효과 → 대상 |
| `gain_reveal_persuasion` | gain | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `gain_reveal_resources` | gain | reveal_card | resources | 7 | solari, spice, water | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `gain_two_reveal_strength` | gain | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `generate_reveal_specimens` | generate_specimens | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `keep_contract_reveal_spice` | keep | reveal_card | none | 3 |  | 한 단계(대상 없음) |
| `lose_reveal_influence_for_vp` | lose_influence | reveal_card | faction | 20 | alliance_recipient, faction | 두 단계: 효과 → 대상 |
| `lose_reveal_troops_for_specimens` | lose_unit | reveal_card | units | 3 | zones | 한 단계(수량: 유닛 조합) |
| `pay_reveal_spice_influence` | pay | reveal_card | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `pay_reveal_water_for_sandworm` | pay | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `place_reveal_spy` | place_spy | reveal_card | post | 78 | post_id | 두 단계: 효과 → 대상 |
| `recall_spies_for_reveal` | recall_spy | reveal_card | post | 78 | first_post_id, second_post_id | 두 단계 + 순서: 회수 → 첫 초소 → 둘째 초소 |
| `recall_spy_for_reveal` | recall_spy | reveal_card | post | 39 | post_id | 두 단계: 효과 → 대상 |
| `recall_spy_for_reveal_placement` | recall_spy | reveal_card | post | 78 | post_id | 두 단계: 효과 → 대상 |
| `recruit_reveal_troops` | recruit | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `resume_reveal_choice` | choose | reveal_card | option | 26 | effect | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `retreat_reveal_card_troop` | retreat | reveal_card | units | 6 | commanders | 한 단계(수량: 유닛 조합) |
| `retreat_two_troops_for_reveal` | retreat | reveal_card | units | 9 | commanders | 한 단계(수량: 유닛 조합) |
| `take_high_council_from_reveal` | take | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `take_reveal_contract` | take | reveal_card | none | 1 |  | 한 단계(대상 없음) |
| `trash_contract_reveal_for_vp` | trash | reveal_card | none | 3 |  | 한 단계(대상 없음) |
| `trash_reveal_card` | trash | reveal_card | personal_card | 404 | card_id | 두 단계: 효과 → 대상 |
| `choose_four_bonus` | choose | scouts | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `choose_subcommittee` | choose | scouts | none | 1 |  | 한 단계(대상 없음) |
| `confirm_scouts_bid` | bid | scouts | none | 1 |  | 한 단계(대상 없음) |
| `decline_subcommittee` | decline | scouts | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `join_subcommittee` | join | scouts | subcommittee | 14 | subcommittee_id | 두 단계: 효과 → 대상 |
| `resolve_scouts_choice_without_option` | resolve_empty | scouts | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `scouts_bid` | bid | scouts | count | 100 | count | 한 단계(수량) |
| `scouts_call` | bid | scouts | count | 100 | count | 한 단계(수량) |
| `scouts_choose_faction` | gain_influence | scouts | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `scouts_choose_option` | choose | scouts | option | 4 | option | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `scouts_collect_mission` | collect | scouts | option | 3 | choice | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `scouts_decline_card` | decline | scouts | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `scouts_decline_mission` | decline | scouts | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `scouts_discard` | discard | scouts | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `scouts_join_mission` | join | scouts | mission | 30 | target | 두 단계: 효과 → 대상 |
| `scouts_lose_garrison_unit` | lose_unit | scouts | units | 2 | commanders | 한 단계(수량: 유닛 조합) |
| `scouts_lose_influence` | lose_influence | scouts | faction | 4 | faction | 두 단계: 효과 → 대상 |
| `scouts_lose_influence_to` | lose_influence | scouts | faction | 16 | alliance_recipient, faction | 두 단계: 효과 → 대상 |
| `scouts_pass` | pass | scouts | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `scouts_recall_agent` | recall_agent | scouts | space | 24 | space_id | 두 단계: 효과 → 대상 |
| `scouts_recall_spy` | recall_spy | scouts | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `scouts_retreat` | retreat | scouts | units | 4 | count | 한 단계(수량: 유닛 조합) |
| `scouts_return_specimens` | return_specimen | scouts | count | 4 | count | 한 단계(수량) |
| `scouts_rewards_first` | collect | scouts | none | 1 |  | 한 단계(대상 없음) |
| `scouts_secret_pick` | bid | scouts | option | 4 | pick | 첫 단계 그 자체(어느 아이콘·갈래·이득) |
| `scouts_take_card` | acquire | scouts | option | 3 | slot | 두 단계: 효과 → 대상 (시장의 칸 = 카드) |
| `scouts_trash_card` | trash | scouts | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `scouts_trash_intrigue` | trash | scouts | intrigue_card | 89 | card_id | 두 단계: 효과 → 대상 |
| `finish_leader_draft` | finish | setup | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `pick_leader` | choose | setup | leader | 18 | leader_id | 두 단계: 효과 → 대상 |
| `decline_gather_intelligence` | decline | spy | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `gather_intelligence` | recall_spy | spy | post | 13 | post_id | 두 단계: 효과 → 대상 |
| `acquire_tech` | acquire | tech | tech | 30 | post_id, tech_id | 두 단계 + 뒤따름: 획득 → 타일 → (Spy를 놓는 타일이면) 초소 |
| `choose_tech_strength` | choose | tech | faction | 21 | alliance_recipient, faction | 두 단계: 효과 → 대상 |
| `choose_tech_trash` | choose | tech | none | 1 |  | 한 단계(대상 없음) |
| `decline_tech` | decline | tech | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `flip_tech` | flip | tech | tech | 3 | tech_id | 두 단계: 효과 → 대상 |
| `place_tech_spy` | place_spy | tech | none | 1 |  | 한 단계(대상 없음) |
| `resolve_tech_acquire_effect` | resolve | tech | tech | 24 | choice, destroy_shield_wall, effect, faction, tech_id | 첫 단계 + 뒤따름: 아이콘 → (진영·방패벽·선택이 있으면) 그 대상 |
| `resolve_tech_influence_without_faction` | resolve_empty | tech | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `draw_owed_card` | draw | trigger | none | 1 |  | 한 단계(대상 없음) |
| `draw_owed_intrigue` | draw | trigger | none | 1 |  | 한 단계(대상 없음) |
| `agent_turn` | place_agent | turn | card_and_space | 26372 | card_id, cost_option, discount, graft, infiltrate_post_id, space_id | B1: 카드 → 칸 |
| `choose_graft_partner` | choose | turn | personal_card | 183 | card_id | 두 단계: 효과 → 대상 |
| `deploy_commanders` | deploy | turn | units | 7 | count | 한 단계(수량: 유닛 조합) |
| `deploy_troops` | deploy | turn | units | 12 | count | 한 단계(수량: 유닛 조합) |
| `finish_agent_turn` | finish | turn | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `finish_reveal` | finish | turn | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `pass_combat_intrigue` | pass | turn | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `pass_endgame_intrigue` | pass | turn | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `play_turn_start_card` | play | turn | personal_card | 1 | card_id | 두 단계: 효과 → 대상 |
| `return_specimen` | return_specimen | turn | none | 1 |  | 한 단계(대상 없음) |
| `reveal_turn` | start_reveal | turn | none | 1 |  | 한 단계(거절·빈 확인·끝내기·넘기기) |
| `use_family_atomics` | use | turn | none | 1 |  | 한 단계(대상 없음) |
| `withdraw_commanders` | withdraw | turn | units | 7 | count | 한 단계(수량: 유닛 조합) |
| `withdraw_troops` | withdraw | turn | units | 12 | count | 한 단계(수량: 유닛 조합) |

합계: 한 단계 149, 두 단계 118, 첫 단계 그 자체 11, 첫 단계 1, B1 1
