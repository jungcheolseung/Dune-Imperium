"use strict";

/* Every string the client writes that is not a rule term, a card, Leader or
   space name, or engine text: { ko, en } by "<file>.<name>". {{name}} is a
   hole the caller fills, {term} a rule term in the current language (see
   t() and tNode() in i18n.js). */
const UI_TEXT = {
  "app.admin_link_invalid": {
    "ko": "관리자 링크가 맞지 않습니다 ({{message}})",
    "en": "The admin link is not valid ({{message}})"
  },
  "app.init_failed": {
    "ko": "초기화 실패 ({{message}})",
    "en": "Initialization failed ({{message}})"
  },
  "board.map_alt": {
    "ko": "듄 임페리움: 봉기 게임판",
    "en": "Dune: Imperium — Uprising board"
  },
  "board.agent_seats": {
    "ko": "{agent}: {{seats}}",
    "en": "{agent}: {{seats}}"
  },
  "board.alliance_holder": {
    "ko": "좌석 {{seat}} · {{faction}} {alliance}",
    "en": "Seat {{seat}} · {{faction}} {alliance}"
  },
  "board.board_scan_missing": {
    "ko": "보드 스캔(assets/board/map.jpg)이 없어 목록으로 표시합니다.",
    "en": "No board scan (assets/board/map.jpg); showing a list instead."
  },
  "board.board_spaces_heading": {
    "ko": "보드 공간",
    "en": "Board spaces"
  },
  "board.bonus_spice": {
    "ko": "보너스 {spice} {{count}}",
    "en": "bonus {spice} {{count}}"
  },
  "board.bonus_spice_label": {
    "ko": "보너스 {spice}",
    "en": "bonus {spice}"
  },
  "board.conflict_deck_remaining": {
    "ko": "교전 카드덱 · {{count}}장 남음",
    "en": "Conflict deck · {{count}} left"
  },
  "board.conflict_not_revealed": {
    "ko": "아직 공개되지 않음",
    "en": "Not revealed yet"
  },
  "board.contract_bank_count": {
    "ko": "남은 {{count}}",
    "en": "bank {{count}}"
  },
  "board.contract_bank_title": {
    "ko": "뒷면으로 쌓인 남은 {contract}",
    "en": "Face-down Contract bank"
  },
  "board.control_seat": {
    "ko": "{control}: 좌석 {{seat}}",
    "en": "{control}: Seat {{seat}}"
  },
  "board.control_seat_space": {
    "ko": "{control}: 좌석 {{seat}} · {{name}}",
    "en": "{control}: Seat {{seat}} · {{name}}"
  },
  "board.flag_combat_space": {
    "ko": "⚔ 전투 장소",
    "en": "⚔ Combat space"
  },
  "board.influence_cube": {
    "ko": "좌석 {{seat}} · {{faction}} {influence_any} {{level}}",
    "en": "Seat {{seat}} · {{faction}} {influence_any} {{level}}"
  },
  "board.intrigue_discard_count": {
    "ko": "{intrigue} {discard_pile} {{count}}장",
    "en": "{intrigue} {discard_pile} {{count}}"
  },
  "board.intrigue_pile_title": {
    "ko": "지금까지 쓰인 {intrigue} 보기",
    "en": "See every {intrigue} played so far"
  },
  "board.intrigue_trash_count": {
    "ko": " · {trash} {{count}}장",
    "en": " · {trash} {{count}}"
  },
  "board.leader_taken": {
    "ko": "선택됨",
    "en": "Taken"
  },
  "board.no_bonus": {
    "ko": "보너스 없음",
    "en": "No bonus"
  },
  "board.no_commanders_on_board": {
    "ko": "보드에 남은 {commander} 없음",
    "en": "No {commander} left on the board"
  },
  "board.space_with_commander": {
    "ko": "{{space}} · {commander} (2 {solari})",
    "en": "{{space}} · {commander} (2 {solari})"
  },
  "board.commander_count": {
    "ko": "{commander} {{count}}",
    "en": "{commander} {{count}}"
  },
  "board.no_human_seats": {
    "ko": "사람 좌석이 없는 게임입니다. 최종 순위의 \"AI 대국 다시 보기\"로 처음부터 볼 수 있습니다.",
    "en": "This game has no human seats. Use \"Watch the AI game again\" in the final standings to watch it from the start."
  },
  "board.pile_intrigue_discard": {
    "ko": "{intrigue} {discard_pile}",
    "en": "{intrigue} {discard_pile}"
  },
  "board.pile_intrigue_trash": {
    "ko": "폐기된 {intrigue}",
    "en": "Trashed Intrigue cards"
  },
  "board.post_seats": {
    "ko": "{{post}}: 좌석 {{seats}}",
    "en": "{{post}}: Seat {{seats}}"
  },
  "board.research_start_short": {
    "ko": "시작",
    "en": "Start"
  },
  "board.research_start_title": {
    "ko": "연구 트랙 시작 칸",
    "en": "Research track start"
  },
  "board.sardaukar_commander_summary": {
    "ko": "{commander} · 보드 {{count}} · 은행 {{bank}}",
    "en": "{commander} · board {{count}} · bank {{bank}}"
  },
  "board.sardaukar_contract_title": {
    "ko": "사다우카 {contract} · 샤담 코리노 4세 전용, 따로 치워둠",
    "en": "Sardaukar {contract} · Shaddam only, set aside"
  },
  "board.seat_conflict_troops": {
    "ko": "좌석 {{seat}} · {conflict} 병력",
    "en": "Seat {{seat}} · {conflict} troops"
  },
  "board.seat_garrison": {
    "ko": "좌석 {{seat}} · {garrison} {{count}}",
    "en": "Seat {{seat}} · {garrison} {{count}}"
  },
  "board.seat_high_council": {
    "ko": "좌석 {{seat}} · 원로회",
    "en": "Seat {{seat}} · High Council"
  },
  "board.seat_maker_hooks": {
    "ko": "좌석 {{seat}} · {maker_hooks}",
    "en": "Seat {{seat}} · {maker_hooks}"
  },
  "board.seat_strength": {
    "ko": "좌석 {{seat}} · 전투력 {{strength}}",
    "en": "Seat {{seat}} · strength {{strength}}"
  },
  "board.seat_vp": {
    "ko": "좌석 {{seat}} · {victory_point} {{vp}}",
    "en": "Seat {{seat}} · {victory_point} {{vp}}"
  },
  "board.set_aside": {
    "ko": "따로 치워둠",
    "en": "set aside"
  },
  "board.shield_wall_destroyed": {
    "ko": "{shield_wall} 파괴됨",
    "en": "{shield_wall} destroyed"
  },
  "board.spice_first_reacher": {
    "ko": "첫 도달자가 가져가는 {spice}",
    "en": "{spice} for whoever gets there first"
  },
  "board.stack_empty": {
    "ko": "더미 {{index}} 비었음",
    "en": "stack {{index}} empty"
  },
  "board.strip_contracts": {
    "ko": "{contract} · 남은 {{count}}장",
    "en": "Contracts · bank {{count}}"
  },
  "board.strip_ixian_embassy": {
    "ko": "익스 대사관 판 · {tech_tile}",
    "en": "Ixian Embassy · Tech tiles"
  },
  "board.strip_leader_draft": {
    "ko": "{leader} 드래프트",
    "en": "{leader} draft"
  },
  "board.strip_reserve": {
    "ko": "{reserve}",
    "en": "Reserve"
  },
  "board.strip_skills": {
    "ko": "공개된 {commander_skill} · 더미 {{count}}",
    "en": "Face-up {commander_skill}s · stack {{count}}"
  },
  "board.strip_tech_trash": {
    "ko": "폐기된 {tech_tile}",
    "en": "Trashed Tech tiles"
  },
  "board.strip_tleilaxu_row": {
    "ko": "{tleilaxu_row} · {deck} {{count}}",
    "en": "{tleilaxu_row} · {deck} {{count}}"
  },
  "board.tleilaxu_track": {
    "ko": "틀레이락스 트랙",
    "en": "Tleilaxu track"
  },
  "board.total_strength": {
    "ko": "전투력 {{strength}}",
    "en": "strength {{strength}}"
  },
  "board.unimplemented_badge": {
    "ko": "미구현 · 배치 불가",
    "en": "Not implemented · cannot place"
  },
  "board.view_full_size": {
    "ko": "크게 보기",
    "en": "View full size"
  },
  "common.seed": {
    "ko": "시드 {{seed}}",
    "en": "seed {{seed}}"
  },
  "common.close": {
    "ko": "닫기",
    "en": "Close"
  },
  "common.collapse": {
    "ko": "접기",
    "en": "Collapse"
  },
  "common.empty": {
    "ko": "비어 있음",
    "en": "Empty"
  },
  "common.expand": {
    "ko": "펼치기",
    "en": "Expand"
  },
  "common.finished": {
    "ko": "종료됨",
    "en": "Finished"
  },
  "common.game_over": {
    "ko": "게임 종료",
    "en": "Game over"
  },
  "common.hidden": {
    "ko": "(비공개)",
    "en": "(hidden)"
  },
  "common.none": {
    "ko": "없음",
    "en": "None"
  },
  "common.release_seat": {
    "ko": "좌석 비우기",
    "en": "Release seat"
  },
  "common.seat": {
    "ko": "좌석 {{seat}}",
    "en": "Seat {{seat}}"
  },
  "core.card_cost": {
    "ko": "비용 {{cost}}",
    "en": "Cost {{cost}}"
  },
  "core.card_persuasion": {
    "ko": "{persuasion} {{amount}}",
    "en": "{persuasion} {{amount}}"
  },
  "core.card_specimens": {
    "ko": "{specimen} {{count}}",
    "en": "{specimen} {{count}}"
  },
  "core.card_swords": {
    "ko": "{sword} {{amount}}",
    "en": "{sword} {{amount}}"
  },
  "core.condition_line": {
    "ko": "조건: {{text}}",
    "en": "Condition: {{text}}"
  },
  "core.conflict_tier": {
    "ko": "{conflict} {{tier}}",
    "en": "{conflict} {{tier}}"
  },
  "core.cost_label": {
    "ko": "비용",
    "en": "Cost"
  },
  "core.intrigue_timings": {
    "ko": "{intrigue} ({{timings}})",
    "en": "{intrigue} ({{timings}})"
  },
  "core.not_implemented": {
    "ko": "미구현 · 배치 불가",
    "en": "Not implemented · cannot place"
  },
  "core.requirement_prefix": {
    "ko": "요구: ",
    "en": "Requires: "
  },
  "core.signet_line": {
    "ko": "인장 반지 능력 — {{name}}: {{text}}",
    "en": "Signet — {{name}}: {{text}}"
  },
  "core.reward_line": {
    "ko": "보상: {{text}}",
    "en": "Reward: {{text}}"
  },
  "core.tech_tile_cost": {
    "ko": "{tech_tile} · 비용 {{cost}} {spice}",
    "en": "{tech_tile} · cost {{cost}} {spice}"
  },
  "core.timing_combat": {
    "ko": "전투",
    "en": "Combat"
  },
  "core.timing_endgame": {
    "ko": "종료 단계",
    "en": "Endgame"
  },
  "core.timing_plot": {
    "ko": "음모",
    "en": "Plot"
  },
  "core.post_name": {
    "ko": "{observation_post} ({{spaces}})",
    "en": "{observation_post} ({{spaces}})"
  },
  "core.research_space": {
    "ko": "연구 트랙 {{column}}-{{row}}",
    "en": "Research track {{column}}-{{row}}"
  },
  "help.announce_confirm_mine": {
    "ko": "{{name}} — 행동을 마쳤습니다. 턴 종료를 확정하세요.",
    "en": "{{name}} — done acting. Confirm the end of turn."
  },
  "help.announce_confirm_other": {
    "ko": "{{name}}의 턴 종료 확정을 기다리는 중",
    "en": "Waiting for {{name}} to confirm the end of turn"
  },
  "help.announce_finished_winner": {
    "ko": "게임 종료 — {{name}} 승리",
    "en": "Game over — {{name}} wins"
  },
  "help.announce_turn_mine": {
    "ko": "{{name}} — 당신 차례입니다: {{prompt}}",
    "en": "{{name}} — your turn: {{prompt}}"
  },
  "help.announce_turn_other": {
    "ko": "{{name}} 차례",
    "en": "{{name}}'s turn"
  },
  "help.icons_heading": {
    "ko": "아이콘",
    "en": "Icons"
  },
  "help.seat_mark_commander": {
    "ko": "{commander} — {garrison}·{conflict}·{supply}에 있는 수",
    "en": "{commander} — count at {garrison} · {conflict} · {supply}"
  },
  "help.seat_mark_conflict": {
    "ko": "{conflict}에 배치한 유닛",
    "en": "Units deployed to the {conflict}"
  },
  "help.seat_mark_first_player": {
    "ko": "{first_player}",
    "en": "{first_player}"
  },
  "help.seat_panel_heading": {
    "ko": "좌석 패널",
    "en": "Seat panel"
  },
  "help.shortcut_cancel": {
    "ko": "고르던 것 취소 · 열린 창 닫기",
    "en": "Cancel a pick · close an open panel"
  },
  "help.shortcut_collapse_columns": {
    "ko": "공용 카드 열을 모두 접기 / 펴기",
    "en": "Collapse / expand all shared card rows"
  },
  "help.shortcut_expand_seats": {
    "ko": "모든 좌석의 자세히 펴기 / 접기",
    "en": "Expand / collapse every seat's detail"
  },
  "help.shortcut_open_help": {
    "ko": "이 도움말 열기",
    "en": "Open this help"
  },
  "help.shortcuts_heading": {
    "ko": "단축키 (한글 입력 상태에서도 됩니다)",
    "en": "Keyboard shortcuts (work even while typing Hangul)"
  },
  "help.title": {
    "ko": "도움말",
    "en": "Help"
  },
  "help.turn_agent": {
    "ko": "{agent_turn}: ① 손패에서 빛나는 카드 → ② 빛나는 칸 → ③ 남은 선택. 칸을 먼저 눌러도 되고, Esc로 취소합니다.",
    "en": "{agent_turn}: ① a highlighted card in hand → ② a highlighted space → ③ any choice left. You can also click the space first; Esc cancels."
  },
  "help.turn_confirm": {
    "ko": "되돌릴 수 있는 동안은 턴이 넘어가지 않습니다. 끝나면 \"턴 종료 확정\"을 누르세요.",
    "en": "The turn does not pass while you can still undo. When done, press \"Confirm end of turn\"."
  },
  "help.turn_heading": {
    "ko": "한 턴 진행",
    "en": "Playing a turn"
  },
  "help.turn_reveal": {
    "ko": "{reveal_turn}: 카드를 공개하고, 남은 {persuasion}으로 빛나는 카드를 산 뒤 끝냅니다.",
    "en": "{reveal_turn}: reveal your cards, acquire highlighted cards with the {persuasion} left, then end."
  },
  "help.turn_undo_limit": {
    "ko": "되돌리기는 자기 연속 행동만 됩니다. 무작위 결과나 숨겨진 정보가 공개된 뒤로는 되돌릴 수 없습니다.",
    "en": "Undo only covers your own run of actions. Once a random result or hidden information is revealed, it cannot be undone."
  },
  "html.board_aria": {
    "ko": "게임 보드",
    "en": "Game board"
  },
  "html.checkpoint_path_label": {
    "ko": "체크포인트 경로 (좌석에 \"학습 체크포인트\"를 고르면 사용; train extra 필요)",
    "en": "Checkpoint path (used when a seat picks \"Training Checkpoint\"; requires the train extra)"
  },
  "html.connection_note": {
    "ko": "서버 연결 끊김 — 다시 연결하는 중…",
    "en": "Server connection lost — reconnecting…"
  },
  "html.create_game": {
    "ko": "게임 시작",
    "en": "Start Game"
  },
  "html.game_list_title": {
    "ko": "진행 중인 게임",
    "en": "Games in Progress"
  },
  "html.host_panel_summary": {
    "ko": "호스트 · 방 링크와 좌석",
    "en": "Host · Room link and seats"
  },
  "html.landing_host_note": {
    "ko": "호스트라면 서버를 띄운 콘솔에 찍힌 관리자 링크를 여세요.",
    "en": "If you're the host, open the admin link printed in the console where you started the server."
  },
  "html.landing_instructions": {
    "ko": "호스트가 보낸 방 링크로 접속하세요.",
    "en": "Use the room link your host sent you."
  },
  "html.landing_resume_button": {
    "ko": "마지막으로 있던 방으로 이어 하기 ▶",
    "en": "Resume your last room ▶"
  },
  "html.landing_title": {
    "ko": "초대받은 사람만 들어올 수 있는 서버입니다",
    "en": "This server is invite-only"
  },
  "html.leave_game": {
    "ko": "나가기",
    "en": "Leave"
  },
  "html.lobby_enter": {
    "ko": "게임 화면으로 ▶",
    "en": "Enter Game ▶"
  },
  "html.lobby_name_label": {
    "ko": "이름 (다른 플레이어에게 보입니다)",
    "en": "Name (visible to other players)"
  },
  "html.lobby_title": {
    "ko": "좌석 고르기",
    "en": "Choose a Seat"
  },
  "html.market_aria": {
    "ko": "공용 카드",
    "en": "Shared cards"
  },
  "html.open_help": {
    "ko": "도움말",
    "en": "Help"
  },
  "html.open_help_title": {
    "ko": "도움말 (?)",
    "en": "Help (?)"
  },
  "html.open_lobby": {
    "ko": "좌석",
    "en": "Seats"
  },
  "html.opt_bloodlines": {
    "ko": "혈통 확장 (사다우카 지휘관·새 카드·지도자 8종)",
    "en": "Bloodlines expansion (Sardaukar Commander · new cards · 8 Leaders)"
  },
  "html.opt_choam": {
    "ko": "초암 모듈",
    "en": "CHOAM Module"
  },
  "html.opt_immortality": {
    "ko": "불멸 확장 (베네 틀레이락스 게임판·틀레이락스 열·접합·새 카드)",
    "en": "Immortality expansion (Bene Tleilax board · Tleilaxu Row · Graft · new cards)"
  },
  "html.opt_leader_draft": {
    "ko": "지도자 6종 공개 드래프트 (OQ-007, 공식 규칙 아님)",
    "en": "Open draft from 6 revealed Leaders (OQ-007, not an official rule)"
  },
  "html.page_title": {
    "ko": "듄 임페리움: 봉기",
    "en": "Dune: Imperium — Uprising"
  },
  "html.opt_promo": {
    "ko": "프로모 카드 (봉기 3장: 아라키스 반란, The Beast's Spoils, Pivotal Gambit; 혈통을 켜면 무자비한 리더십, 불멸을 켜면 틀레이락스 덱에 천재적인 조언자, 파이터도)",
    "en": "Promo cards (3 in Uprising: Arrakis Revolt, The Beast's Spoils, Pivotal Gambit; plus Ruthless Leadership with Bloodlines on, and Piter, Genius Advisor in the Tleilaxu deck with Immortality on)"
  },
  "html.opt_seed_label": {
    "ko": "시드 (빈칸 = 무작위)",
    "en": "Seed (blank = random)"
  },
  "html.opt_seed_placeholder": {
    "ko": "무작위",
    "en": "Random"
  },
  "html.opt_tech": {
    "ko": "기술 모듈 (혈통 필요: 익스 대사관 판·기술 타일 18장·익스의 코타 오닥스)",
    "en": "Tech Module (requires Bloodlines: Ixian Embassy · 18 Tech tiles · Kota Odax)"
  },
  "html.private_zone_aria": {
    "ko": "내 손패",
    "en": "My hand"
  },
  "html.review_exit": {
    "ko": "검토 종료",
    "en": "Exit review"
  },
  "html.review_first": {
    "ko": "처음으로",
    "en": "First"
  },
  "html.review_interval_025": {
    "ko": "0.25초",
    "en": "0.25s"
  },
  "html.review_interval_05": {
    "ko": "0.5초",
    "en": "0.5s"
  },
  "html.review_interval_1": {
    "ko": "1초",
    "en": "1s"
  },
  "html.review_interval_2": {
    "ko": "2초",
    "en": "2s"
  },
  "html.review_interval_4": {
    "ko": "4초",
    "en": "4s"
  },
  "html.review_interval_label": {
    "ko": "간격",
    "en": "Interval"
  },
  "html.review_last": {
    "ko": "끝으로",
    "en": "Last"
  },
  "html.review_next": {
    "ko": "다음 수",
    "en": "Next move"
  },
  "html.review_prev": {
    "ko": "이전 수",
    "en": "Previous move"
  },
  "html.review_seat_label": {
    "ko": "검토 좌석",
    "en": "Review seat"
  },
  "html.review_slider_aria": {
    "ko": "검토 위치",
    "en": "Review position"
  },
  "html.review_unit_label": {
    "ko": "단위",
    "en": "Unit"
  },
  "html.review_unit_step": {
    "ko": "한 수씩",
    "en": "Per move"
  },
  "html.review_unit_turn": {
    "ko": "한 턴씩",
    "en": "Per turn"
  },
  "html.rule_options_legend": {
    "ko": "규칙 옵션",
    "en": "Rule Options"
  },
  "html.save_game": {
    "ko": "저장",
    "en": "Save"
  },
  "html.save_list_title": {
    "ko": "저장된 게임",
    "en": "Saved Games"
  },
  "html.seat_assignment_legend": {
    "ko": "좌석 배정",
    "en": "Seat Assignment"
  },
  "html.seats_aria": {
    "ko": "좌석",
    "en": "Seats"
  },
  "html.setup_title": {
    "ko": "새 게임",
    "en": "New Game"
  },
  "panels.agent_remaining": {
    "ko": "남은 {agent}",
    "en": "{agent} remaining"
  },
  "panels.agents_placed_label": {
    "ko": "배치",
    "en": "Placed"
  },
  "panels.battle_label": {
    "ko": "배틀 아이콘 카드",
    "en": "Battle"
  },
  "panels.chairdog_return": {
    "ko": "의자개: {reveal_turn} 시작 때 {hand}로 {{cards}}",
    "en": "Chairdog: returns to {hand} at the start of {reveal_turn} — {{cards}}"
  },
  "panels.commander_where": {
    "ko": "{{where}}의 {commander} {{count}}",
    "en": "{{where}} {commander} {{count}}"
  },
  "panels.completed_suffix": {
    "ko": " (완료)",
    "en": " (completed)"
  },
  "panels.contracts_label": {
    "ko": "{contract}",
    "en": "Contracts"
  },
  "panels.control_spaces": {
    "ko": "{control}: {{spaces}}",
    "en": "{control}: {{spaces}}"
  },
  "panels.deck_top_badge": {
    "ko": "덱 맨 위",
    "en": "Top of deck"
  },
  "panels.discard_pile_view": {
    "ko": "{discard_pile} 보기",
    "en": "View {discard_pile}"
  },
  "panels.facedown_suffix": {
    "ko": " (뒤집힘)",
    "en": " (face-down)"
  },
  "panels.first_badge": {
    "ko": "시작",
    "en": "1st"
  },
  "panels.flip_suffix": {
    "ko": " (뒤집힘)",
    "en": " (Flipped)"
  },
  "panels.hand_empty": {
    "ko": "손패 없음",
    "en": "No cards in hand"
  },
  "panels.hand_public_label": {
    "ko": "{hand} (공개) ",
    "en": "Hand (public) "
  },
  "panels.in_play_label": {
    "ko": "플레이 영역",
    "en": "In play"
  },
  "panels.intrigue_deck_top_badge": {
    "ko": "책략 카드덱 맨 위",
    "en": "Top of Intrigue deck"
  },
  "panels.intrigue_resolving_label": {
    "ko": "{intrigue} 해결 중 ",
    "en": "Intrigue resolving "
  },
  "panels.leader_unset": {
    "ko": "{leader} 미정",
    "en": "{leader} not chosen yet"
  },
  "panels.log_heading": {
    "ko": "행동 로그",
    "en": "Action log"
  },
  "panels.high_council": {
    "ko": "원로회",
    "en": "High Council"
  },
  "panels.swordmaster": {
    "ko": "소드마스터",
    "en": "Swordmaster"
  },
  "panels.family_atomics": {
    "ko": "가문 핵 토큰",
    "en": "Family Atomics"
  },
  "panels.maker_hooks": {
    "ko": "{maker_hooks}",
    "en": "{maker_hooks}"
  },
  "panels.my_discard": {
    "ko": "내 {discard_pile}",
    "en": "My discard pile"
  },
  "panels.seat_discard": {
    "ko": "{{seat}}의 {discard_pile}",
    "en": "{{seat}}'s discard pile"
  },
  "panels.my_hand": {
    "ko": "내 손패 · {{seat}}",
    "en": "My hand · {{seat}}"
  },
  "panels.navigation_remaining": {
    "ko": "{navigation} {{count}}장 남음",
    "en": "{{count}} Navigation cards remaining"
  },
  "panels.neutral_combat_intrigue": {
    "ko": "전투 책략 카드 창",
    "en": "Combat Intrigue window"
  },
  "panels.neutral_combat_resolved": {
    "ko": "전투 해결",
    "en": "Combat resolved"
  },
  "panels.neutral_default": {
    "ko": "게임 진행",
    "en": "Game in progress"
  },
  "panels.neutral_round_started": {
    "ko": "라운드 {{round}} 시작",
    "en": "Round {{round}} started"
  },
  "panels.neutral_round_started_generic": {
    "ko": "라운드 시작",
    "en": "Round started"
  },
  "panels.neutral_setup": {
    "ko": "게임 준비",
    "en": "Game setup"
  },
  "panels.reveal_preview_prefix": {
    "ko": "지금 공개하면 ",
    "en": "If revealed now: "
  },
  "panels.revealed": {
    "ko": "{reveal_turn} 마침",
    "en": "{reveal_turn} done"
  },
  "panels.review_replay_button": {
    "ko": "리플레이 검토",
    "en": "Review replay"
  },
  "panels.review_start_failed": {
    "ko": "검토 시작 실패 ({{message}})",
    "en": "Failed to start review ({{message}})"
  },
  "panels.seat_hand": {
    "ko": "{{name}}의 손패",
    "en": "{{name}}'s hand"
  },
  "panels.seat_more_collapse": {
    "ko": "자세히 ▾",
    "en": "Details ▾"
  },
  "panels.seat_more_expand": {
    "ko": "자세히 ▸ · {{summary}}",
    "en": "Details ▸ · {{summary}}"
  },
  "panels.secret_project": {
    "ko": "Secret Project (뒷면 {tech_tile})",
    "en": "Secret Project (face-down {tech_tile})"
  },
  "panels.skills_label": {
    "ko": "{commander_skill}",
    "en": "Skills"
  },
  "panels.spy_boxed": {
    "ko": "상자로 돌아간 {spy} {{count}}",
    "en": "{spy} back in the box: {{count}}"
  },
  "panels.standings_garrison_header": {
    "ko": "{garrison} {troop}",
    "en": "Garrison"
  },
  "panels.standings_heading": {
    "ko": "최종 순위",
    "en": "Final standings"
  },
  "panels.standings_rank_header": {
    "ko": "순위",
    "en": "Rank"
  },
  "panels.standings_seat_header": {
    "ko": "좌석",
    "en": "Seat"
  },
  "panels.standings_solari_header": {
    "ko": "{solari}",
    "en": "Solari"
  },
  "panels.standings_spice_header": {
    "ko": "{spice}",
    "en": "Spice"
  },
  "panels.standings_vp_header": {
    "ko": "{victory_point}",
    "en": "VP"
  },
  "panels.standings_water_header": {
    "ko": "{water}",
    "en": "Water"
  },
  "panels.status_label": {
    "ko": "상태",
    "en": "Status"
  },
  "panels.supply_spy": {
    "ko": "{supply}의 {spy}",
    "en": "{spy} in {supply}"
  },
  "panels.tactics_space": {
    "ko": "전술 트랙 {{space}}칸",
    "en": "Tactics space {{space}}"
  },
  "panels.tech_label": {
    "ko": "{tech_tile}",
    "en": "Tech"
  },
  "panels.twisted_deck": {
    "ko": "뒤틀린 책략 카드덱 {{count}}",
    "en": "Twisted Intrigue deck {{count}}"
  },
  "panels.undo_row": {
    "ko": "↩ 좌석 {{seat}}이(가) {{count}}단계 되돌림",
    "en": "↩ Seat {{seat}} undid {{count}} step(s)"
  },
  "panels.undone_suffix": {
    "ko": " (되돌림)",
    "en": " (undone)"
  },
  "panels.usurp_trash": {
    "ko": "Usurp: 차례 끝에 {{card}} {trash}",
    "en": "Usurp: {trash} {{card}} at end of turn"
  },
  "panels.watch_ai_button": {
    "ko": "AI 대국 다시 보기",
    "en": "Watch the AI game again"
  },
  "panels.you_badge": {
    "ko": "나",
    "en": "YOU"
  },
  "panels.you_named": {
    "ko": "나 · {{name}}",
    "en": "YOU · {{name}}"
  },
  "render.acquire_cost_label": {
    "ko": "비용",
    "en": "Cost"
  },
  "render.action_focus_label": {
    "ko": "{{label}} · 선택지 {{count}}개",
    "en": "{{label}} · {{count}} option(s)"
  },
  "render.bought_cards_label": {
    "ko": "산 카드: ",
    "en": "Cards acquired: "
  },
  "render.buyable_cards_heading": {
    "ko": "살 수 있는 카드 — 테이블에서 빛나는 카드를 눌러도 됩니다",
    "en": "Cards you can acquire — you can also click the highlighted cards on the table"
  },
  "render.confirm_count_label": {
    "ko": "{{count}}개 {{label}}",
    "en": "{{count}} {{label}}"
  },
  "render.confirm_short": {
    "ko": "확정",
    "en": "Confirm"
  },
  "render.confirm_turn_button": {
    "ko": "턴 종료 확정 ▶",
    "en": "Confirm end of turn ▶"
  },
  "render.confirm_turn_meta": {
    "ko": "되돌릴 수 있는 동안은 턴이 넘어가지 않습니다 · 다음: {{next}}",
    "en": "The turn does not pass while it can still be undone · Next: {{next}}"
  },
  "render.confirm_turn_prompt": {
    "ko": "행동을 마쳤습니다. 턴을 넘길까요?",
    "en": "Actions are done. Hand over the turn?"
  },
  "render.contract_bank": {
    "ko": "남은 계약",
    "en": "Contract bank"
  },
  "render.count_step_down": {
    "ko": "하나 적게",
    "en": "One fewer"
  },
  "render.count_step_up": {
    "ko": "하나 더",
    "en": "One more"
  },
  "render.deck_conflict": {
    "ko": "교전 카드덱",
    "en": "Conflict deck"
  },
  "render.deck_imperium": {
    "ko": "임페리움 카드덱",
    "en": "Imperium deck"
  },
  "render.deck_intrigue": {
    "ko": "책략 카드덱",
    "en": "Intrigue deck"
  },
  "render.deck_order_line": {
    "ko": "{deck} 순서 ({{count}})",
    "en": "{deck} order ({{count}})"
  },
  "render.disclosure_closed_note": {
    "ko": "검토 중인 시점의 모든 {hand}와 {deck} 순서가 들어 있어, 펼치면 앞으로 뽑힐 카드가 보입니다.",
    "en": "Includes every {hand} and {deck} order as of the reviewed point — expanding it shows cards about to be drawn."
  },
  "render.disclosure_title": {
    "ko": "종료 후 공개 (모든 비공개 존)",
    "en": "Post-game disclosure (all private zones)"
  },
  "render.effect_preview_title": {
    "ko": "효과 미리보기",
    "en": "Effect preview"
  },
  "render.finish_reveal": {
    "ko": "{reveal_turn} 종료",
    "en": "End {reveal_turn}"
  },
  "render.finish_reveal_with_buys": {
    "ko": "구매 끝 · {reveal_turn} 종료",
    "en": "Done acquiring · End {reveal_turn}"
  },
  "render.free": {
    "ko": "무료",
    "en": "Free"
  },
  "render.game_over_no_standings": {
    "ko": "게임이 끝났습니다.",
    "en": "The game has ended."
  },
  "render.game_over_winner": {
    "ko": "게임 종료 — {{winner}} 승리",
    "en": "Game over — {{winner}} wins"
  },
  "render.hand_line": {
    "ko": "{hand} ({{count}})",
    "en": "{hand} ({{count}})"
  },
  "render.in_progress": {
    "ko": "진행 중…",
    "en": "In progress…"
  },
  "render.intrigue_line": {
    "ko": "{intrigue} ({{count}})",
    "en": "{intrigue} ({{count}})"
  },
  "render.irreversible_badge": {
    "ko": "되돌리기 불가",
    "en": "Cannot undo"
  },
  "render.irreversible_title": {
    "ko": "이 행동 뒤에는 되돌릴 수 없습니다 (숨겨진 정보가 공개되거나 무작위 결과가 정해집니다)",
    "en": "This action cannot be undone afterward (it reveals hidden information or fixes a random outcome)"
  },
  "render.margin_all_tied": {
    "ko": "{{vp}} 동점 · 동점 판정 항목도 모두 같아 {reveal_turn}를 더 늦게 마친 좌석이 승리",
    "en": "{{vp}} tied · every tiebreaker equal too — the seat that finished a {reveal_turn} more recently wins"
  },
  "render.margin_tiebreak": {
    "ko": "{{vp}} 동점 · 동점 판정 {{tiebreak}} {{first}} 대 {{second}}",
    "en": "{{vp}} tied · tiebreaker {{tiebreak}}: {{first}} vs {{second}}"
  },
  "render.margin_vp": {
    "ko": "{{vp}} ({{diff}} 차)",
    "en": "{{vp}} ({{diff}} ahead)"
  },
  "render.next_label": {
    "ko": "다음: {{name}}",
    "en": "Next: {{name}}"
  },
  "render.persuasion_remaining": {
    "ko": "남은 {persuasion} ",
    "en": "{persuasion} left "
  },
  "render.replay_review": {
    "ko": "리플레이 검토",
    "en": "Replay review"
  },
  "render.reveal_effects_heading": {
    "ko": "{reveal_turn} 효과",
    "en": "{reveal_turn} effects"
  },
  "render.reveal_preview_title": {
    "ko": "지금 손패를 공개하면 바로 얻는 {persuasion}과 {strength} ({reveal_turn} 중의 선택 효과는 제외)",
    "en": "The {persuasion} and {strength} gained immediately by revealing your hand now (excludes optional effects during the {reveal_turn})"
  },
  "render.badge_choam": {
    "ko": "초암 모듈",
    "en": "CHOAM"
  },
  "render.badge_promo": {
    "ko": "프로모 카드",
    "en": "promo"
  },
  "render.badge_bloodlines": {
    "ko": "혈통",
    "en": "Bloodlines"
  },
  "render.badge_tech": {
    "ko": "기술 모듈",
    "en": "Tech"
  },
  "render.badge_immortality": {
    "ko": "불멸",
    "en": "Immortality"
  },
  "render.badge_draft": {
    "ko": "지도자 드래프트",
    "en": "draft"
  },
  "render.round_status": {
    "ko": "라운드 {{round}} · {{phase}}",
    "en": "Round {{round}} · {{phase}}"
  },
  "render.seat_you": {
    "ko": "좌석 {{seat}} (당신)",
    "en": "Seat {{seat}} (you)"
  },
  "render.second_place": {
    "ko": " · 2위 {{name}}",
    "en": " · 2nd place {{name}}"
  },
  "render.shared_deck_order_title": {
    "ko": "공용 덱 순서",
    "en": "Shared deck order"
  },
  "render.shortfall_specimens": {
    "ko": "{supply} 부족: {specimen} {{requested}}개 중 {{made}}개만 생성",
    "en": "Short {supply}: only {{made}} of {{requested}} {specimen} made"
  },
  "render.shortfall_title": {
    "ko": "선택은 할 수 있지만 {supply}가 부족해 인쇄된 만큼 되지 않습니다",
    "en": "You can still choose, but the {supply} is short, so it does less than printed"
  },
  "render.shortfall_troops": {
    "ko": "{supply} 부족: {troop} {{requested}}개 중 {{made}}개만 {recruit}",
    "en": "Short {supply}: only {{made}} of {{requested}} {troop} recruited"
  },
  "render.spectating_ai": {
    "ko": "AI 대국 관전",
    "en": "Watching the AI match"
  },
  "render.strength_preview_title": {
    "ko": "이 행동 뒤의 내 {strength}",
    "en": "My {strength} after this action"
  },
  "render.undo_all_steps": {
    "ko": "{{steps}}단계 모두 되돌리기",
    "en": "Undo all {{steps}} steps"
  },
  "render.undo_one_step": {
    "ko": "되돌리기 (1단계)",
    "en": "Undo (1 step)"
  },
  "render.view_all": {
    "ko": "전체 보기",
    "en": "View all"
  },
  "render.waiting_confirm": {
    "ko": "{{name}}의 턴 종료 확정을 기다리는 중…",
    "en": "Waiting for {{name}} to confirm end of turn…"
  },
  "render.waiting_decision": {
    "ko": "{{name}} 결정 대기 중…",
    "en": "Waiting for {{name}}'s decision…"
  },
  "render.waiting_hint_empty": {
    "ko": " (아직 아무도 앉지 않은 좌석입니다 — 방 링크를 보내 주세요)",
    "en": " (nobody has taken this seat yet — send the room link)"
  },
  "render.waiting_hint_offline": {
    "ko": " (접속이 끊겨 있습니다)",
    "en": " (disconnected)"
  },
  "review.before_game_start": {
    "ko": "게임 시작 전",
    "en": "Before the game started"
  },
  "core.chance_label": {
    "ko": "무작위 결과: {{decision}}",
    "en": "Random outcome: {{decision}}"
  },
  "core.chance_discard_shuffle": {
    "ko": "{{seat}}의 {discard_pile} 섞기",
    "en": "{{seat}}'s {discard_pile} shuffled"
  },
  "core.chance_intrigue_shuffle": {
    "ko": "{intrigue} {discard_pile} 섞기",
    "en": "{intrigue} {discard_pile} shuffled"
  },
  "core.chance_secrets_steal": {
    "ko": "{{thief}}, {{victim}}에게서 {steal_intrigue}",
    "en": "{{thief}}: {steal_intrigue} from {{victim}}"
  },
  "core.chance_other": {
    "ko": "기타",
    "en": "other"
  },
  "review.chance_values": {
    "ko": "{{count}}장 · {{names}} …",
    "en": "{{count}} card(s) · {{names}} …"
  },
  "review.next_own_action": {
    "ko": "다음 {{own}} 행동",
    "en": "{{own}} next action"
  },
  "review.own_mine": {
    "ko": "내",
    "en": "My"
  },
  "review.own_seat": {
    "ko": "이 좌석",
    "en": "This seat's"
  },
  "review.pause": {
    "ko": "일시정지",
    "en": "Pause"
  },
  "review.play": {
    "ko": "재생",
    "en": "Play"
  },
  "review.prev_own_action": {
    "ko": "이전 {{own}} 행동",
    "en": "{{own}} previous action"
  },
  "review.replay_from_start": {
    "ko": "처음부터 재생",
    "en": "Replay from start"
  },
  "review.round_label": {
    "ko": "라운드 {{round}}",
    "en": "Round {{round}}"
  },
  "review.seat_option": {
    "ko": "좌석 {{seat}} ({{kind}})",
    "en": "Seat {{seat}} ({{kind}})"
  },
  "review.span_extra": {
    "ko": "{{opening}} 외 {{extra}}수",
    "en": "{{opening}} plus {{extra}} more move(s)"
  },
  "review.status_fetch_failed": {
    "ko": "검토 상태 조회 실패 ({{message}})",
    "en": "Failed to load review status ({{message}})"
  },
  "review.step_count": {
    "ko": "수 {{cursor}}/{{total}}",
    "en": "step {{cursor}}/{{total}}"
  },
  "review.step_label": {
    "ko": "좌석 {{seat}}: {{action}}",
    "en": "Seat {{seat}}: {{action}}"
  },
  "review.undo_marker": {
    "ko": " · ↩ 좌석 {{seat}}: 여기서 {{count}}단계 되돌림: ",
    "en": " · ↩ Seat {{seat}}: rewound {{count}} step(s) here: "
  },
  "review.watch_failed": {
    "ko": "관전 시작 실패 ({{message}})",
    "en": "Failed to start watching ({{message}})"
  },
  "screens.autosave_badge": {
    "ko": "자동 저장",
    "en": "Autosave"
  },
  "screens.continue_button": {
    "ko": "이어서",
    "en": "Continue"
  },
  "screens.copy_button": {
    "ko": "복사",
    "en": "Copy"
  },
  "screens.create_game_failed": {
    "ko": "게임 생성 실패 ({{message}})",
    "en": "Game creation failed ({{message}})"
  },
  "screens.delete_button": {
    "ko": "삭제",
    "en": "Delete"
  },
  "screens.empty_seat": {
    "ko": "빈 좌석",
    "en": "Empty seat"
  },
  "screens.game_fetch_failed": {
    "ko": "게임 조회 실패 ({{message}})",
    "en": "Game fetch failed ({{message}})"
  },
  "screens.game_not_found": {
    "ko": "그 게임은 이 서버에 없습니다 (서버가 다시 시작됐을 수 있습니다).",
    "en": "That game isn't on this server (the server may have restarted)."
  },
  "screens.game_state_failed": {
    "ko": "게임 상태 조회 실패 ({{message}})",
    "en": "Game state fetch failed ({{message}})"
  },
  "screens.leave_seat": {
    "ko": "자리 비우기",
    "en": "Leave seat"
  },
  "screens.load_button": {
    "ko": "불러오기",
    "en": "Load"
  },
  "screens.load_failed": {
    "ko": "불러오기 실패 ({{message}})",
    "en": "Load failed ({{message}})"
  },
  "screens.lobby_status": {
    "ko": "라운드 {{round}} · {{phase}}",
    "en": "Round {{round}} · {{phase}}"
  },
  "screens.my_seat": {
    "ko": "내 좌석",
    "en": "My seat"
  },
  "screens.name_required": {
    "ko": "이름을 먼저 적어 주세요.",
    "en": "Enter your name first."
  },
  "screens.no_free_seats": {
    "ko": "빈 좌석이 없습니다. 호스트에게 좌석을 비워 달라고 하세요.",
    "en": "No free seats. Ask the host to free one up."
  },
  "screens.no_saves_yet": {
    "ko": "아직 이 게임의 저장이 없습니다.",
    "en": "No saves for this game yet."
  },
  "screens.offline": {
    "ko": "접속 끊김",
    "en": "Offline"
  },
  "screens.online": {
    "ko": "접속 중",
    "en": "Online"
  },
  "screens.person": {
    "ko": "사람",
    "en": "Human"
  },
  "screens.player_label": {
    "ko": "좌석 {{seat}} ({{name}})",
    "en": "Seat {{seat}} ({{name}})"
  },
  "screens.refresh_list_button": {
    "ko": "목록 새로 고침",
    "en": "Refresh list"
  },
  "screens.release_seat_failed": {
    "ko": "좌석 비우기 실패 ({{message}})",
    "en": "Couldn't release the seat ({{message}})"
  },
  "screens.request_failed": {
    "ko": "요청 실패 ({{message}})",
    "en": "Request failed ({{message}})"
  },
  "screens.room_link_heading": {
    "ko": "방 링크 — 친구들에게 이 주소 하나를 보내세요",
    "en": "Room link — send friends this one address"
  },
  "screens.round_number": {
    "ko": "라운드 {{round}}",
    "en": "Round {{round}}"
  },
  "screens.save_list_error": {
    "ko": "저장 목록을 읽지 못했습니다 ({{error}})",
    "en": "Couldn't read the save list ({{error}})"
  },
  "screens.save_now_button": {
    "ko": "지금 저장",
    "en": "Save now"
  },
  "screens.save_recovery_hint": {
    "ko": "서버가 죽으면: 서버를 다시 띄우고 관리자 링크로 들어가 자동 저장을 불러온 뒤, 새 방 링크를 보내세요.",
    "en": "If the server dies: restart it, open it with the admin link, load the autosave, then send a new room link."
  },
  "screens.saves_heading_auto": {
    "ko": "저장 — 턴이 넘어갈 때마다 자동 저장됩니다",
    "en": "Saves — autosaved every turn"
  },
  "screens.saves_heading_manual": {
    "ko": "저장 — 자동 저장이 꺼져 있습니다 (--no-autosave)",
    "en": "Saves — autosave is off (--no-autosave)"
  },
  "screens.seat_left": {
    "ko": "좌석에서 내려왔습니다. 다시 앉으려면 좌석을 고르세요.",
    "en": "You left your seat. Pick a seat to sit again."
  },
  "screens.seat_taken": {
    "ko": "방금 다른 사람이 그 좌석에 앉았습니다.",
    "en": "Someone else just sat in that seat."
  },
  "screens.server_address_label": {
    "ko": "친구들이 접속하는 서버 주소 (예: http://100.x.y.z:8000)",
    "en": "Server address your friends connect to (e.g. http://100.x.y.z:8000)"
  },
  "screens.sit_button": {
    "ko": "앉기",
    "en": "Sit"
  },
  "screens.sit_failed": {
    "ko": "앉기 실패 ({{message}})",
    "en": "Sit failed ({{message}})"
  },
  "screens.unnamed_save": {
    "ko": "이름 없는 저장",
    "en": "Unnamed save"
  },
  "screens.view_save_list_button": {
    "ko": "저장 목록 보기",
    "en": "View save list"
  },
  "session.action_failed": {
    "ko": "행동 적용 실패 ({{message}})",
    "en": "Action failed ({{message}})"
  },
  "session.game_deleted": {
    "ko": "이 게임은 서버에서 삭제되었습니다.",
    "en": "This game was deleted on the server."
  },
  "session.game_missing": {
    "ko": "이 게임은 서버에 더 이상 없습니다. 서버가 다시 시작됐다면 호스트가 자동 저장을 불러온 뒤 보내는 새 방 링크로 들어오세요.",
    "en": "This game no longer exists on the server. If the server restarted, join with the new room link the host sends after loading the autosave."
  },
  "session.my_turn_title": {
    "ko": "▶ 내 차례 — {{title}}",
    "en": "▶ My turn — {{title}}"
  },
  "session.save_failed": {
    "ko": "저장 실패 ({{message}})",
    "en": "Save failed ({{message}})"
  },
  "session.save_name_prompt": {
    "ko": "저장 이름 (비워도 됩니다)",
    "en": "Save name (optional)"
  },
  "session.saved": {
    "ko": "저장됨: {{name}}",
    "en": "Saved: {{name}}"
  },
  "session.turn_end_failed": {
    "ko": "턴 종료 실패 ({{message}})",
    "en": "Turn end failed ({{message}})"
  },
  "session.undo_failed": {
    "ko": "되돌리기 실패 ({{message}})",
    "en": "Undo failed ({{message}})"
  },
  "turn.choose": {
    "ko": "고르세요",
    "en": "Choose"
  },
  "turn.choose_again": {
    "ko": "다시 고르기",
    "en": "Choose again"
  },
  "turn.discount_suffix": {
    "ko": " 할인",
    "en": " discount"
  },
  "turn.graft_pending": {
    "ko": "{graft} — 함께 낼 카드는 다음에 고릅니다",
    "en": "{graft} — choose the card to play together next"
  },
  "turn.graft_solo": {
    "ko": "이 카드만",
    "en": "This card only"
  },
  "turn.hint_both_picked": {
    "ko": "두 카드로 갈 수 있는 칸이 빛납니다. 보낼 곳을 누르세요. (Esc: 취소)",
    "en": "Spaces that fit both cards are highlighted. Click where to send them. (Esc: cancel)"
  },
  "turn.hint_choose_card": {
    "ko": "빛나는 카드 중에서 그 칸에 낼 카드를 누르세요. (Esc: 취소)",
    "en": "Click one of the highlighted cards to play there. (Esc: cancel)"
  },
  "turn.hint_choose_space": {
    "ko": "빛나는 칸 중에서 {agent}를 보낼 곳을 누르세요. (Esc: 취소)",
    "en": "Click a highlighted space to send your {agent} there. (Esc: cancel)"
  },
  "turn.hint_graft_optional": {
    "ko": "빛나는 칸을 누르세요. {graft}으로 함께 낼 카드가 있으면 ＋ 표시된 카드를 먼저 누르세요. (Esc: 취소)",
    "en": "Click a highlighted space. If a card can join by {graft}, click the one marked ＋ first. (Esc: cancel)"
  },
  "turn.hint_graft_required": {
    "ko": "{graft} 카드는 혼자 낼 수 없습니다. ＋ 표시된 카드를 눌러 함께 낼 카드를 고르거나, 칸을 먼저 눌러도 됩니다.",
    "en": "A {graft} card cannot be played alone. Click a card marked ＋ to choose one to play together, or click a space first."
  },
  "turn.hint_start": {
    "ko": "손패에서 빛나는 카드를 누르세요. 칸을 먼저 눌러도 됩니다.",
    "en": "Click a highlighted card in your hand. You can also click a space first."
  },
  "turn.multiple_choices": {
    "ko": "{{name}}: 선택지가 {{count}}개입니다. 오른쪽 행동 목록에서 고르세요.",
    "en": "{{name}}: {{count}} choices available. Choose from the action list on the right."
  },
  "turn.no_discount": {
    "ko": "할인 없이",
    "en": "No discount"
  },
  "turn.no_route": {
    "ko": "{{from}} → {{to}}: 갈 수 없습니다.",
    "en": "{{from}} → {{to}}: not possible."
  },
  "turn.or": {
    "ko": "또는",
    "en": "Or"
  },
  "turn.partner_not_allowed": {
    "ko": "{{name}}: 이 칸에서 함께 낼 수 없습니다. 함께 낼 카드를 다시 고르거나 되돌리기를 누르세요.",
    "en": "{{name}}: cannot be played together on this space. Choose a different card to play together, or undo."
  },
  "turn.show_full_list": {
    "ko": "전체 행동 목록 보기 ({{count}}개)",
    "en": "Show full action list ({{count}})"
  },
  "turn.show_steps": {
    "ko": "단계별로 고르기",
    "en": "Choose step by step"
  },
  "turn.spy_recall": {
    "ko": "{recall_spy} — {{post}}",
    "en": "{recall_spy} — {{post}}"
  },
  "turn.spy_recall_none": {
    "ko": "{spy} 소환 없이",
    "en": "No {spy} recall"
  },
  "turn.step3_hint": {
    "ko": "③ 남은 선택을 고르세요.",
    "en": "③ Make the remaining choices."
  },
  "turn.step_card": {
    "ko": "카드",
    "en": "Card"
  },
  "turn.step_space": {
    "ko": "보낼 칸",
    "en": "Space"
  },
  "turn.step_together": {
    "ko": "함께",
    "en": "Together"
  },
  "turn.table_hint": {
    "ko": "테이블에서 빛나는 카드나 칸을 눌러 골라도 됩니다.",
    "en": "You can also click a highlighted card or space on the table."
  }
};
