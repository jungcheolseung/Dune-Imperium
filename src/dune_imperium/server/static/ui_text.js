"use strict";

/* Every string the client writes that is not a rule term, a card, Leader or
   space name, or engine text: { ko, en } by "<file>.<name>". {{name}} is a
   hole the caller fills, {term} a rule term in the current language (see
   t() and tNode() in i18n.js). */
const UI_TEXT = {
  "card_faces.or": { "ko": "—또는—", "en": "—OR—" },
  "html.open_encyclopedia": { "ko": "카드 백과 ▶", "en": "Card encyclopedia ▶" },
  "gallery.no_face": { "ko": "앞면 그림 준비 중 — 카드 글", "en": "Face not drawn yet — the card's text" },
  "gallery.tech_module": { "ko": "기술 모듈", "en": "Tech Module" },
  "gallery.kind_objectives": { "ko": "목적 카드", "en": "Objectives" },
  "gallery.title": { "ko": "카드 백과", "en": "Card encyclopedia" },
  "gallery.kind_cards": { "ko": "임페리움·틀레이락스 카드", "en": "Imperium & Tleilaxu cards" },
  "gallery.kind_intrigue": { "ko": "책략 카드", "en": "Intrigue cards" },
  "gallery.kind_conflicts": { "ko": "교전 카드", "en": "Conflict cards" },
  "gallery.kind_contracts": { "ko": "계약 타일", "en": "Contracts" },
  "gallery.kind_tech": { "ko": "기술 타일", "en": "Tech tiles" },
  "gallery.kind_leaders": { "ko": "지도자", "en": "Leaders" },
  "gallery.kind_skills": { "ko": "사다우카 지휘관 기술 토큰", "en": "Sardaukar Commander Skills" },
  "gallery.set_all": { "ko": "전체", "en": "All" },
  "gallery.set_starting": { "ko": "시작 카드", "en": "Starting deck" },
  "gallery.set_imperium": { "ko": "원판", "en": "Dune: Imperium" },
  "gallery.set_ix": { "ko": "익스의 부상", "en": "Rise of Ix" },
  "gallery.set_immortality": { "ko": "불멸", "en": "Immortality" },
  "gallery.set_uprising": { "ko": "봉기", "en": "Uprising" },
  "gallery.set_bloodlines": { "ko": "혈통", "en": "Bloodlines" },
  "gallery.promo": { "ko": "프로모", "en": "Promo" },
  "gallery.choam": { "ko": "초암 모듈", "en": "CHOAM Module" },
  "gallery.search": { "ko": "이름으로 찾기 (한국어·영어)", "en": "Search by name (English or Korean)" },
  "gallery.none": { "ko": "찾는 카드가 없습니다.", "en": "No card matches." },
  "gallery.rulings": { "ko": "이 게임에서 정한 판정", "en": "This game's rulings" },
  "gallery.pictures": { "ko": "그림 점검", "en": "Picture check" },
  "gallery.size": { "ko": "크기", "en": "Size" },
  "card_faces.first": { "ko": "등", "en": "st" },
  "card_faces.second": { "ko": "등", "en": "nd" },
  "card_faces.third": { "ko": "등", "en": "rd" },
  "clock.game_title": { "ko": "게임 시간", "en": "Game time" },
  "clock.seat_title": { "ko": "{{name}} 사용 시간", "en": "Time used by {{name}}" },
  "clock.spell_title": {
    "ko": "{{name}} 이번 차례 시간",
    "en": "{{name}}'s time this turn"
  },
  "clock.since_load": {
    "ko": "이 판을 불러온 뒤부터 센 시간",
    "en": "counted since the game was loaded"
  },
  "clock.totals_game": { "ko": "게임 시간 {{time}}", "en": "Game time {{time}}" },
  "clock.totals_seat": { "ko": "{{name}} {{time}}", "en": "{{name}} {{time}}" },
  "board.seat_specimens": {
    "ko": "플레이어{{seat}} · {specimen} {{count}}",
    "en": "Player {{seat}} · {specimen} {{count}}"
  },
  "board.conflict_history_button": { "ko": "교전 이력", "en": "History" },
  "panels.conflict_history": { "ko": "교전 카드 이력", "en": "Conflict card history" },
  "panels.conflict_history_open": {
    "ko": "{{name}} · 클릭하여 교전 카드 이력 보기",
    "en": "{{name}} · Click to view Conflict card history"
  },
  "panels.conflict_history_current": { "ko": "현재", "en": "Current" },
  "panels.conflict_history_back": {
    "ko": "← 교전 카드 이력",
    "en": "← Conflict card history"
  },
  "panels.vp_ledger_open": {
    "ko": "{victory_point} {{points}} · 클릭하여 얻은 기록 보기",
    "en": "{victory_point} {{points}} · Click to see how they were scored"
  },
  "panels.win_odds_heading": { "ko": "형세 흐름", "en": "How the game went" },
  "panels.win_odds_note": {
    "ko": "라운드가 시작할 때 각 좌석이 1등 할 확률입니다. 탐색 AI가 그때 모두가 보던 정보만으로 판단했습니다(AI 넷이 이어 둔다고 칠 때).",
    "en": "Each seat's chance of first place at the start of each round, as the search AI judged it from what the whole table could see then (as if four AIs played on)."
  },
  "panels.win_odds_loading": { "ko": "형세를 계산하는 중…", "en": "Working out how the game went…" },
  "panels.win_odds_point": { "ko": "{{round}}라운드: {{odds}}", "en": "Round {{round}}: {{odds}}" },
  "panels.win_odds_aria": {
    "ko": "형세 흐름: {{first}}~{{last}}라운드 시작 때 각 좌석이 1등 할 확률",
    "en": "How the game went: each seat's chance of first place at the start of rounds {{first}} to {{last}}"
  },
  "panels.win_odds_round_header": { "ko": "라운드", "en": "Round" },
  "panels.vp_ledger_title": {
    "ko": "{{name}} · {victory_point} 기록 (현재 {{points}})",
    "en": "{{name}} · {victory_point} history (now {{points}})"
  },
  "panels.vp_ledger_note": {
    "ko": "행을 누르면 행동 기록에서 그 단계를 찾아 줍니다.",
    "en": "Click a row to find its step in the action log."
  },
  "panels.vp_ledger_loading": { "ko": "불러오는 중…", "en": "Loading…" },
  "panels.vp_ledger_failed": {
    "ko": "기록을 불러오지 못했습니다: {{message}}",
    "en": "Could not load the history: {{message}}"
  },
  "panels.vp_ledger_start": { "ko": "게임 시작", "en": "Game start" },
  "panels.vp_ledger_round": { "ko": "R{{round}}", "en": "R{{round}}" },
  "panels.vp_ledger_total": {
    "ko": "이 단계 뒤 {{points}}",
    "en": "{{points}} after this step"
  },
  "panels.vp_ledger_find": {
    "ko": "행동 기록에서 이 단계 보기",
    "en": "Show this step in the action log"
  },
  "panels.vp_ledger_steps": { "ko": "라운드별 기록", "en": "Round by round" },
  "panels.vp_part_heading": { "ko": "점수 구성", "en": "What the points are made of" },
  "panels.vp_part_start": { "ko": "시작 점수", "en": "Starting points" },
  "panels.vp_part_influence": { "ko": "영향력", "en": "Influence" },
  "panels.vp_part_alliance": { "ko": "동맹", "en": "Alliances" },
  "panels.vp_part_spice_must_flow": { "ko": "스파이스는 흘러야 한다", "en": "The Spice Must Flow" },
  "panels.vp_part_conflict": { "ko": "교전 보상", "en": "Conflict rewards" },
  "panels.vp_part_battle_icons": { "ko": "배틀 아이콘 짝", "en": "Battle icon matches" },
  "panels.vp_part_intrigue": { "ko": "책략 카드", "en": "Intrigue cards" },
  "panels.vp_part_card": { "ko": "카드 효과", "en": "Card effects" },
  "panels.vp_part_tleilaxu": { "ko": "틀레이락스 트랙", "en": "Tleilaxu track" },
  "panels.vp_part_tech": { "ko": "기술 타일", "en": "Tech tiles" },
  "panels.vp_part_other": { "ko": "기타", "en": "Other" },
  "panels.vp_part_total": { "ko": "합계", "en": "Total" },
  "panels.vp_part_item_points": { "ko": "{{points}}점", "en": "{{points}} VP" },
  "effects.agent": { "ko": "에이전트 카드 사용", "en": "Agent card played" },
  "effects.played": { "ko": "카드 사용", "en": "Card played" },
  "effects.graft": { "ko": "접합 카드 사용", "en": "Graft card played" },
  "effects.intrigue": { "ko": "책략 카드 사용", "en": "Intrigue played" },
  "effects.combat_intrigue": { "ko": "전투 책략 사용", "en": "Combat Intrigue played" },
  "effects.navigation": { "ko": "운항 카드 사용", "en": "Navigation card played" },
  "effects.banner_round": { "ko": "라운드 {{round}}", "en": "Round {{round}}" },
  "effects.banner_conflict": { "ko": "{conflict}: {{name}}", "en": "{conflict}: {{name}}" },
  "effects.banner_turn_mine": { "ko": "내 차례", "en": "Your turn" },
  "effects.banner_turn_other": { "ko": "플레이어{{seat}} 차례", "en": "Player {{seat}}'s turn" },
  "effects.result_title": { "ko": "전투 결과", "en": "Combat Result" },
  "effects.result_unranked": { "ko": "보상 없음", "en": "No reward" },
  "effects.result_double": { "ko": "모래벌레: 보상 2배", "en": "Sandworm: reward doubled" },
  "effects.result_close": { "ko": "누르면 닫힙니다", "en": "Click to close" },
  "effects.banner_sandworm": { "ko": "{sandworm} 부름!", "en": "Sandworm summoned!" },
  "effects.banner_sandworms": { "ko": "{sandworm} {{count}}마리 부름!", "en": "{{count}} sandworms summoned!" },
  "effects.banner_shield_wall": { "ko": "{shield_wall} 파괴!", "en": "{shield_wall} destroyed!" },
  "effects.banner_alliance": { "ko": "{{alliance}} 획득!", "en": "{{alliance}} gained!" },
  "effects.banner_alliance_lost": { "ko": "{{alliance}} 상실", "en": "{{alliance}} lost" },
  "effects.alliance_from": { "ko": "{{name}}에게서 가져옴", "en": "Taken from {{name}}" },
  "effects.final_title": { "ko": "최종 순위", "en": "Final Standings" },
  "effects.final_winner": { "ko": "승자: {{name}}", "en": "Winner: {{name}}" },
  "effects.rank_1": { "ko": "1위", "en": "1st" },
  "effects.rank_2": { "ko": "2위", "en": "2nd" },
  "effects.rank_3": { "ko": "3위", "en": "3rd" },
  "effects.rank_4": { "ko": "4위", "en": "4th" },
  "screens.ai_pace_normal": { "ko": "보통", "en": "Normal" },
  "screens.ai_pace_fast": { "ko": "빠르게", "en": "Fast" },
  "screens.ai_pace_instant": { "ko": "즉시", "en": "Instant" },
  "screens.ai_pace_header": { "ko": "AI: {{pace}}", "en": "AI: {{pace}}" },
  "html.opt_ai_pace_label": { "ko": "AI 진행 속도", "en": "AI pace" },
  "html.ai_pace_title": {
    "ko": "AI 진행 속도 — 보통은 AI의 차례와 카드를 하나씩 보여 주고, 즉시는 기다리지 않습니다",
    "en": "AI pace — Normal shows each AI turn and card in turn; Instant does not wait"
  },
  "html.setup_intro": {
    "ko": "플레이어와 규칙을 고르고 아라키스로 떠나세요.",
    "en": "Choose your players and rules. Arrakis awaits."
  },
  "screens.setup_summary": {
    "ko": "사람 {{human}}명 · AI {{ai}}명 · 규칙 옵션 {{options}}개 선택",
    "en": "{{human}} human · {{ai}} AI · {{options}} rule options selected"
  },
  "panels.log_compact": {
    "ko": "기록 줄이기",
    "en": "Compact history"
  },
  "panels.log_expand": {
    "ko": "기록 크게 보기",
    "en": "Expand history"
  },
  "app.admin_link_invalid": {
    "ko": "관리자 링크가 맞지 않습니다 ({{message}})",
    "en": "The admin link is not valid ({{message}})"
  },
  "app.init_failed": {
    "ko": "초기화 실패 ({{message}})",
    "en": "Initialization failed ({{message}})"
  },
  "board.map_alt_imperium": {
    "ko": "듄: 임페리움 게임판",
    "en": "Dune: Imperium board"
  },
  "board.known_intrigue_top": {
    "ko": "내가 아는 책략 카드덱 맨 위: {{card}}",
    "en": "You know the Intrigue deck's top card: {{card}}"
  },
  "board.known_intrigue_bottom": {
    "ko": "내가 아는 책략 카드덱 맨 아래: {{cards}}",
    "en": "You know at the Intrigue deck's bottom: {{cards}}"
  },
  "board.known_intrigue_at_bottom": {
    "ko": "{{card}}(맨 아래)",
    "en": "{{card}} (the bottom card)"
  },
  "board.known_intrigue_above": {
    "ko": "{{card}}(맨 아래에서 {{depth}}장 위)",
    "en": "{{card}} ({{depth}} above the bottom card)"
  },
  "board.snooper_token": {
    "ko": "탐지기 토큰 · {{faction}} 영향력 2칸",
    "en": "Snooper token · {{faction}} Influence 2"
  },
  "board.map_alt_ix": {
    "ko": "익스 게임판",
    "en": "Ix board"
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
    "ko": "플레이어{{seat}} · {{faction}} {alliance}",
    "en": "Player {{seat}} · {{faction}} {alliance}"
  },
  "board.board_scan_missing": {
    "ko": "게임판 스캔(assets/board/uprising.jpg)이 없어 목록으로 표시합니다.",
    "en": "No board scan (assets/board/uprising.jpg); showing a list instead."
  },
  "board.board_spaces_heading": {
    "ko": "게임판 장소",
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
  "board.mentat_here": {
    "ko": "멘타트 있음",
    "en": "The Mentat is here"
  },
  "board.mentat_owed": {
    "ko": "다음 라운드에 {{seat}}",
    "en": "{{seat}} next round"
  },
  "board.voice_blocked": {
    "ko": "{{card}}: {{seats}} 막힘",
    "en": "{{card}}: barred to {{seats}}"
  },
  "board.control_seat": {
    "ko": "{control}: 플레이어{{seat}}",
    "en": "{control}: Player {{seat}}"
  },
  "board.control_seat_space": {
    "ko": "{control}: 플레이어{{seat}} · {{name}}",
    "en": "{control}: Player {{seat}} · {{name}}"
  },
  "board.flag_combat_space": {
    "ko": "⚔ 전투 장소",
    "en": "⚔ Combat space"
  },
  "board.space_agent_icon": {
    "ko": "에이전트 아이콘: {{icon}}",
    "en": "Agent icon: {{icon}}"
  },
  "board.space_cost_now": {
    "ko": "지금 적용",
    "en": "applies now"
  },
  "board.influence_cube": {
    "ko": "플레이어{{seat}} · {{faction}} {influence_any} {{level}}",
    "en": "Player {{seat}} · {{faction}} {influence_any} {{level}}"
  },
  "board.intrigue_discard_count": {
    "ko": "{intrigue_card} {discard_pile} {{count}}장",
    "en": "{intrigue_card} {discard_pile} {{count}}"
  },
  "board.intrigue_deck_count": {
    "ko": "책략 카드덱 {{count}}장",
    "en": "Intrigue deck {{count}}"
  },
  "board.intrigue_pile_title": {
    "ko": "{intrigue_card} {discard_pile} 보기",
    "en": "See the {intrigue_card} {discard_pile}"
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
    "ko": "게임판에 남은 {commander} 없음",
    "en": "No {commander} left on the board"
  },
  "board.space_with_commander": {
    "ko": "{{space}} · {commander}",
    "en": "{{space}} · {commander}"
  },
  "board.no_human_seats": {
    "ko": "사람 플레이어가 없는 게임입니다. 최종 순위의 \"AI 대국 다시 보기\"로 처음부터 볼 수 있습니다.",
    "en": "This game has no human players. Use \"Watch the AI game again\" in the final standings to watch it from the start."
  },
  "board.pile_intrigue_discard": {
    "ko": "{intrigue_card} {discard_pile}",
    "en": "{intrigue_card} {discard_pile}"
  },
  "board.post_seats": {
    "ko": "{{post}}: {{seats}}",
    "en": "{{post}}: {{seats}}"
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
    "ko": "{commander} · 게임판 {{count}} · 은행 {{bank}}",
    "en": "{commander} · board {{count}} · bank {{bank}}"
  },
  "board.scouts_piece": {
    "ko": "{{mission}} · {{goods}} ({{who}})",
    "en": "{{mission}} · {{goods}} ({{who}})"
  },
  "board.seat_conflict_units": {
    "ko": "플레이어{{seat}} · {conflict}: {{units}}",
    "en": "Player {{seat}} · {conflict}: {{units}}"
  },
  "board.seat_garrison_units": {
    "ko": "플레이어{{seat}} · {garrison}: {{units}}",
    "en": "Player {{seat}} · {garrison}: {{units}}"
  },
  "board.dreadnought_control_leaving": {
    "ko": "플레이어{{seat}}의 드레드노트 · {{name}} 지배 · 다음 전투 단계가 끝나면 주둔지로",
    "en": "Player {{seat}}'s dreadnought · controls {{name}} · back to the garrison when the next Combat phase ends"
  },
  "board.dreadnought_control_staying": {
    "ko": "플레이어{{seat}}의 드레드노트 · {{name}} 지배 · 다음 라운드 전투 단계까지",
    "en": "Player {{seat}}'s dreadnought · controls {{name}} · through the next round's Combat phase"
  },
  "board.seat_freighter": {
    "ko": "플레이어{{seat}} · 화물선 · 운송 트랙 {{step}}칸",
    "en": "Player {{seat}} · Freighter · Shipping track step {{step}}"
  },
  "board.seat_high_council": {
    "ko": "플레이어{{seat}} · 원로회",
    "en": "Player {{seat}} · High Council"
  },
  "board.seat_maker_hooks": {
    "ko": "플레이어{{seat}} · {maker_hooks}",
    "en": "Player {{seat}} · {maker_hooks}"
  },
  "board.seat_negotiators": {
    "ko": "플레이어{{seat}} · 협상가 {{count}}",
    "en": "Player {{seat}} · Negotiators {{count}}"
  },
  "board.seat_strength": {
    "ko": "플레이어{{seat}} · 전투력 {{strength}}",
    "en": "Player {{seat}} · strength {{strength}}"
  },
  "board.seat_vp": {
    "ko": "플레이어{{seat}} · {victory_point} {{vp}}",
    "en": "Player {{seat}} · {victory_point} {{vp}}"
  },
  "board.set_aside": {
    "ko": "따로 치워둠",
    "en": "set aside"
  },
  "board.spice_first_reacher": {
    "ko": "첫 도달자가 가져가는 {spice}",
    "en": "{spice} for whoever gets there first"
  },
  "board.stack_empty": {
    "ko": "더미 {{index}} 비었음",
    "en": "stack {{index}} empty"
  },
  "board.tech_stack_count": {
    "ko": "이 더미의 기술 타일 {{count}}개 (맨 위 포함)",
    "en": "{{count}} Tech tiles in this stack (the top one included)"
  },
  "board.strip_contracts": {
    "ko": "{contract} · 남은 {{count}}개",
    "en": "Contracts · bank {{count}}"
  },
  "board.strip_imperium_row": {
    "ko": "{imperium_row} · {deck} {{count}}",
    "en": "{imperium_row} · {deck} {{count}}"
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
    "ko": "플레이어 해제",
    "en": "Release player"
  },
  "common.seat": {
    "ko": "플레이어{{seat}}",
    "en": "Player {{seat}}"
  },
  "core.server_unreachable": {
    "ko": "서버에 연결하지 못했습니다",
    "en": "Could not reach the server"
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
    "ko": "{intrigue_card} ({{timings}})",
    "en": "{intrigue_card} ({{timings}})"
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
  "core.signet_line_unnamed": {
    "ko": "인장 반지 능력 — {{text}}",
    "en": "Signet — {{text}}"
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
  "core.intrigue_line": {
    "ko": "{{n}}번째 줄",
    "en": "line {{n}}"
  },
  "core.source_combat_reward": {
    "ko": "{conflict} 보상",
    "en": "{conflict} Reward"
  },
  "help.announce_finished_winner": {
    "ko": "게임 종료 — {{name}} 승리",
    "en": "Game over — {{name}} wins"
  },
  "help.announce_turn_mine": {
    "ko": "{{name}} — 당신 차례입니다: {{prompt}}",
    "en": "{{name}} — your turn: {{prompt}}"
  },
  "help.announce_turn_end_mine": {
    "ko": "{{name}} — 할 일을 마쳤습니다. 턴 종료를 누르세요.",
    "en": "{{name}} — done. Press End turn."
  },
  "help.announce_turn_end_other": {
    "ko": "{{name}}의 턴 종료를 기다리는 중",
    "en": "Waiting for {{name}} to end the turn"
  },
  "help.announce_turn_other": {
    "ko": "{{name}} 차례",
    "en": "{{name}}'s turn"
  },
  "help.icons_heading": {
    "ko": "아이콘",
    "en": "Icons"
  },
  "help.rulings_app_differs": {
    "ko": "공식은 말이 없고, 앱과 다르게 정한 곳 ({{count}})",
    "en": "The official rules are silent and this game differs from the app ({{count}})"
  },
  "help.rulings_base_ix": {
    "ko": "원판 듄: 임페리움·익스의 부상",
    "en": "base game · Rise of Ix"
  },
  "help.rulings_engine_pending": {
    "ko": "엔진 반영 전 — 지금은 이전 판정대로 동작",
    "en": "not in the engine yet — the game still plays the earlier ruling"
  },
  "help.rulings_heading": {
    "ko": "이 게임에서 정한 판정",
    "en": "Rulings made for this game"
  },
  "help.rulings_intro": {
    "ko": "공식 룰북·FAQ가 정하지 않았거나 출처(룰북·FAQ, 디자이너 답변, 공식 디지털판 앱)끼리 말이 다른 곳에서 이 게임이 정한 판정입니다.",
    "en": "How this game rules the points the official rulebook and FAQ leave open, or where the sources (rulebook and FAQ, the designer's answers, the official digital app) disagree."
  },
  "help.rulings_project": {
    "ko": "공식이 정하지 않아 이 게임이 정한 곳 ({{count}})",
    "en": "The official rules are silent and this game decided ({{count}})"
  },
  "help.rulings_sources": {
    "ko": "출처: {{sources}}",
    "en": "Sources: {{sources}}"
  },
  "help.rulings_sources_differ": {
    "ko": "출처끼리 말이 달라 하나를 고른 곳 ({{count}})",
    "en": "Sources disagree and one was chosen ({{count}})"
  },
  "help.seat_mark_hand": {
    "ko": "핸드의 카드 수",
    "en": "Cards in the hand"
  },
  "help.seat_mark_deck": {
    "ko": "카드덱의 카드 수 (핸드·카드덱·버림 더미를 누르면 목록)",
    "en": "Cards in the deck (click the hand, deck or discard pile for the lists)"
  },
  "help.seat_mark_memories": {
    "ko": "레이디 제시카의 기억 (스파이스의 고통으로 게임판의 베네 게세리트 영역에 옮긴 병력)",
    "en": "Lady Jessica's memories (troops Spice Agony moved to the Bene Gesserit board area)"
  },
  "help.seat_mark_commander": {
    "ko": "{supply}에 있는 {commander} 수 ({garrison}·{conflict}에 있는 것은 게임판에 그려짐)",
    "en": "{commander} count in {supply} (those in the {garrison} or the {conflict} are drawn on the board)"
  },
  "help.seat_mark_clock": {
    "ko": "결정권을 쥔 시간의 합(사람·AI 모두). 강조된 것이 지금 흐르는 시계이고, 머리글 오른쪽의 시간은 게임 시간",
    "en": "Total time holding control (humans and AI alike). The highlighted one is running; the time at the right of the header is the game time"
  },
  "help.seat_mark_first_player": {
    "ko": "{first_player}",
    "en": "{first_player}"
  },
  "help.seat_panel_heading": {
    "ko": "플레이어 패널",
    "en": "Player panel"
  },
  "help.shortcut_cancel": {
    "ko": "고르던 것 취소 · 열린 창 닫기",
    "en": "Cancel a pick · close an open panel"
  },
  "help.shortcut_collapse_columns": {
    "ko": "공용 카드 열을 모두 접기 / 펴기",
    "en": "Collapse / expand all shared card rows"
  },
  "help.shortcut_scouts_card": {
    "ko": "게임판 위 아라킨 스카웃 카드 접기 / 펴기 (이번 라운드에 공개된 항목이 있을 때)",
    "en": "Fold away / bring back the Arrakeen Scouts card over the board (when this round revealed an item)"
  },
  "help.shortcut_layout": {
    "ko": "열 사이 경계를 끌면 열 너비가 바뀝니다(두 번 클릭: 기본값). 핸드의 카드와 {intrigue}는 끌거나 Alt+←/→로 순서를 바꿉니다. 둘 다 이 브라우저에만 저장됩니다.",
    "en": "Drag the line between two columns to resize them (double-click: default). Drag a card in your hand or an {intrigue}, or press Alt+←/→, to reorder it. Both are kept in this browser only."
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
    "ko": "{agent_turn}: ① 핸드에서 빛나는 카드 → ② 빛나는 장소 → ③ 남은 선택. 장소를 먼저 눌러도 되고, Esc로 취소합니다.",
    "en": "{agent_turn}: ① a highlighted card in hand → ② a highlighted space → ③ any choice left. You can also click the space first; Esc cancels."
  },
  "help.turn_confirm": {
    "ko": "차례는 \"턴 종료 ▶\"를 한 번 눌러야 넘어갑니다. 누르기 전에는 되돌릴 수 있는 행동을 되돌릴 수 있습니다. 차례 밖에서 한 번 보내면 되돌릴 수 없는 선택(곧바로 다음 라운드로 이어지는 보상 등)은 고르기만 해 두었다가 \"확정 ▶\"으로 보냅니다.",
    "en": "A turn passes only when you press \"End turn ▶\" once. Until then you can take back what can still be undone. Outside your turns, a choice that could not be taken back once sent (a reward that runs straight into the next round, say) is only picked first and sent with \"Confirm ▶\"."
  },
  "help.screen_heading": { "ko": "이 화면", "en": "This screen" },
  "help.effects_label": {
    "ko": "화면 연출 (카드 알림, 차례·라운드 안내, 전투 결과판, 말과 카드의 움직임)",
    "en": "Table effects (card cues, turn and round banners, combat results, moving pieces and cards)"
  },
  "help.effects_note": {
    "ko": "이 브라우저에만 남습니다. 꺼도 소리와 기록은 그대로입니다.",
    "en": "Kept in this browser only. Sounds and the log stay as they are."
  },
  "help.game_settings_heading": {
    "ko": "이 판의 설정",
    "en": "This game's setup"
  },
  "help.turn_heading": {
    "ko": "한 차례 진행",
    "en": "Playing a turn"
  },
  "help.turn_reveal": {
    "ko": "{reveal_turn}: 카드를 공개하고, 남은 {persuasion}으로 빛나는 카드를 획득한 뒤 끝냅니다.",
    "en": "{reveal_turn}: reveal your cards, acquire highlighted cards with the {persuasion} left, then end."
  },
  "help.turn_scouts": {
    "ko": "아라킨 스카웃: 각 라운드 첫 차례 전에 그 라운드의 항목을 차례로 처리합니다(오른쪽 패널). 비밀 선택과 봉인 입찰액은 다른 플레이어에게 보이지 않고, 입찰은 액수를 고른 뒤 \"턴 종료 ▶\"가 곧 확정입니다.",
    "en": "Arrakeen Scouts: before each round's first turn, each player handles the round's item in turn (panel on the right). Secret picks and sealed bids stay hidden from the other players; pick a bid, then \"End turn ▶\" confirms it."
  },
  "help.turn_undo_limit": {
    "ko": "되돌리기는 자기 연속 행동만 됩니다. 무작위 결과나 숨겨진 정보가 공개된 뒤로는 되돌릴 수 없습니다.",
    "en": "Undo only covers your own run of actions. Once a random result or hidden information is revealed, it cannot be undone."
  },
  "html.board_aria": {
    "ko": "게임판",
    "en": "Game board"
  },
  "html.checkpoint_path_label": {
    "ko": "체크포인트 경로 (플레이어 유형에서 \"학습 체크포인트\"를 고르면 사용)",
    "en": "Checkpoint path (used when a player selects \"Training Checkpoint\")"
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
    "ko": "호스트 · 방 링크와 플레이어",
    "en": "Host · Room link and players"
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
    "ko": "플레이어 고르기",
    "en": "Choose a Player"
  },
  "html.market_aria": {
    "ko": "공용 카드",
    "en": "Shared cards"
  },
  "html.open_help": {
    "ko": "도움말",
    "en": "Help"
  },
  "html.panel_toggles_open": {
    "ko": "보기 ▾",
    "en": "View ▾"
  },
  "html.panel_toggles_aria": {
    "ko": "패널",
    "en": "Panels"
  },
  "html.panel_hand": {
    "ko": "핸드",
    "en": "Hand"
  },
  "html.panel_seats": {
    "ko": "플레이어",
    "en": "Players"
  },
  "html.panel_market": {
    "ko": "공용 카드",
    "en": "Shared cards"
  },
  "html.panel_log": {
    "ko": "기록",
    "en": "Log"
  },
  "html.phone_board_zoom": {
    "ko": "확대",
    "en": "Zoom"
  },
  "html.phone_menu": {
    "ko": "메뉴",
    "en": "Menu"
  },
  "html.phone_tabs_aria": {
    "ko": "화면",
    "en": "Views"
  },
  "html.phone_tab_board": {
    "ko": "게임판",
    "en": "Board"
  },
  "html.phone_tab_hand": {
    "ko": "핸드",
    "en": "Hand"
  },
  "html.phone_tab_seats": {
    "ko": "플레이어",
    "en": "Players"
  },
  "html.phone_tab_market": {
    "ko": "공용 카드",
    "en": "Shared"
  },
  "html.phone_tab_log": {
    "ko": "기록",
    "en": "Log"
  },
  "html.open_help_title": {
    "ko": "도움말 (?)",
    "en": "Help (?)"
  },
  "html.bt_zoom_label": {
    "ko": "{bene_tleilax_board}",
    "en": "{bene_tleilax_board}"
  },
  "html.open_lobby": {
    "ko": "플레이어",
    "en": "Players"
  },
  "html.opt_bloodlines": {
    "ko": "혈통 확장 (사다우카 지휘관·새 카드·지도자 8종)",
    "en": "Bloodlines expansion (Sardaukar Commander · new cards · 8 Leaders)"
  },
  "html.opt_choam": {
    "ko": "초암 모듈",
    "en": "CHOAM Module"
  },
  "html.opt_go_to_11": {
    "ko": "11점을 향해 (불멸 필요: 모두 승점 0에서 시작, 종료 점수는 그대로)",
    "en": "Go to 11 (requires Immortality: everyone starts at 0 VP; the end score stays the same)"
  },
  "html.opt_first_player_seat_zero": {
    "ko": "플레이어1이 시작 플레이어 (사막쥐 목적 카드는 플레이어1에게, 나머지 목적 카드는 무작위; 공식 규칙 아님)",
    "en": "Player 1 starts (Player 1 gets the Desert Mouse Objective, the other Objectives are dealt at random; not an official rule)"
  },
  "html.opt_epic_game": {
    "ko": "에픽 게임 모드 (12점까지 · 교전 I 없이 II·III 5장씩 · 주둔지 병력 5·책략 카드 1장으로 시작 · 사막 행성 듄 1장 대신 스파이스를 지배하라)",
    "en": "Epic Game Mode (play to 12 · no Conflict I, five II over five III · start with 5 garrison troops and an Intrigue card · Control the Spice for one Dune, the Desert Planet)"
  },
  "html.opt_immortality": {
    "ko": "불멸 확장 (베네 틀레이락스 게임판·틀레이락스 열·접합·새 카드)",
    "en": "Immortality expansion (Bene Tleilax board · Tleilaxu Row · Graft · new cards)"
  },
  "html.opt_base_game_label": {
    "ko": "기본 판",
    "en": "Base game"
  },
  "html.opt_base_game_uprising": {
    "ko": "듄 임페리움: 봉기",
    "en": "Dune: Imperium — Uprising"
  },
  "html.opt_base_game_imperium": {
    "ko": "듄: 임페리움 (원판)",
    "en": "Dune: Imperium (the original game)"
  },
  "html.base_game_imperium_note": {
    "ko": "원판은 아직 플레이어1 시작 플레이어·지도자 드래프트·프로모 카드(원판 3장)·익스의 부상 확장·불멸 확장(11점을 향해 포함)·혈통 확장·아라킨 스카웃과, 익스의 부상과 함께일 때 에픽 게임 모드만 함께 씁니다. 원판의 혈통은 원판에 맞지 않는 카드와 지도자를 빼고(혈통 지도자 6종), 기술 모듈은 기술 타일 12장으로 쓰며, 익스의 부상과 함께면 익스 대사관 없이 익스 게임판에서 두 확장의 기술 타일 30장을 씁니다. 아라킨 스카웃은 앱의 원판 일정(관측 초소를 쓰지 않는 항목)을 쓰고, 초암 모듈은 원판과 함께 쓰지 않습니다. 원판 판에는 앱 AI·휴리스틱 AI·랜덤 AI와, 서버에 원판용 망이 있으면 탐색 AI가 앉습니다(롤아웃 AI는 아직 원판을 두지 않습니다).",
    "en": "The original game takes only Player 1 as First Player, the Leader draft, the promo cards (its 3), the Rise of Ix expansion, the Immortality expansion (Go to 11 included), the Bloodlines expansion, Arrakeen Scouts and, with Rise of Ix, Epic Game Mode so far. Bloodlines leaves out the cards and Leaders that do not fit the original game (6 Bloodlines Leaders), its Tech Module plays 12 Tech tiles, and with Rise of Ix there is no Ixian Embassy: both expansions' 30 Tech tiles go on the Ix board. Arrakeen Scouts plays the app's original-game schedule (items without observation posts), and the CHOAM module is not played with the original game. The app AI, the heuristic AI and the random AI sit at an original table, and so does the search AI where the server has its original-game network (the rollout AIs do not play the original game yet)."
  },
  "screens.base_game_imperium_badge": {
    "ko": "원판",
    "en": "Original"
  },
  "html.opt_scouts": {
    "ko": "아라킨 스카웃 (컴패니언 앱 모드: 소위원회·임무·이벤트·경매·판매, 공식 규칙서 없음)",
    "en": "Arrakeen Scouts (companion app mode: subcommittees · missions · events · auctions · sales; no official rulebook)"
  },
  "html.opt_leader_draft": {
    "ko": "지도자 6종 공개 드래프트 (공식 규칙 아님)",
    "en": "Open draft from 6 revealed Leaders (not an official rule)"
  },
  "html.page_title": {
    "ko": "듄: 임페리움",
    "en": "Dune: Imperium"
  },
  "html.opt_promo": {
    "ko": "프로모 카드 (봉기 3장: 아라키스 반란, The Beast's Spoils, Pivotal Gambit; 혈통을 켜면 무자비한 리더십, 불멸을 켜면 틀레이락스 덱에 천재적인 조언자, 파이터, 원판 카드를 켜면 원판 3장 Duncan, Loyal Blade · Jessica of Arrakis · Thumper도)",
    "en": "Promo cards (3 in Uprising: Arrakis Revolt, The Beast's Spoils, Pivotal Gambit; plus Ruthless Leadership with Bloodlines on, Piter, Genius Advisor in the Tleilaxu deck with Immortality on, and the original game's 3, Duncan, Loyal Blade · Jessica of Arrakis · Thumper, with Original cards on)"
  },
  "html.opt_promo_imperium": {
    "ko": "프로모 카드 (원판 3장: Duncan, Loyal Blade · Jessica of Arrakis · Thumper; 혈통을 켜면 무자비한 리더십, 불멸을 켜면 틀레이락스 덱에 천재적인 조언자, 파이터도)",
    "en": "Promo cards (3 in the original game: Duncan, Loyal Blade · Jessica of Arrakis · Thumper; plus Ruthless Leadership with Bloodlines on, and Piter, Genius Advisor in the Tleilaxu deck with Immortality on)"
  },
  "html.opt_imperium_cards": {
    "ko": "원판 카드 (봉기에서만: 듄: 임페리움 원판의 임페리움 카드·책략 카드를 Calculated Hire만 빼고 모두, 지도자 8종도 함께 섞음)",
    "en": "Original cards (Uprising only: the original Dune: Imperium's Imperium and Intrigue cards, all but Calculated Hire, and its 8 Leaders shuffled in)"
  },
  "html.uprising_ix_note": {
    "ko": "봉기와 익스의 부상: 초암 게임판 덮개를 반만 펴 게임판 오른쪽 위(회의장·지원자 모집·운송·계약 수락과 그 관측소 둘)를 덮고, 익스 게임판을 옆에 둡니다. 덮개와 익스 게임판에는 관측소가 하나씩 있는 것으로 칩니다. 익스의 교전 카드는 넣지 않습니다. 초암 모듈과 함께면 각자 익스 계약 2장을 받아 시작 계약 하나를 몰래 고르고(모두 고르면 공개), 아라킨 스카웃과 함께면 지원 제공 임무 대신 익스 임무 셋(비자금·무장 경호·밀항자)을 씁니다.",
    "en": "Uprising with Rise of Ix: the CHOAM board overlay, unfolded halfway, covers the board's top-right corner (Assembly Hall, Gather Support, Shipping, Accept Contract and their two observation posts), and the Ix board lies beside it. The overlay and the Ix board each count as having one observation post. Rise of Ix's Conflict cards stay out. With the CHOAM module each player is given two Rise of Ix contracts and secretly chooses one to start with (revealed once all have chosen); with Arrakeen Scouts, Rise of Ix's three missions (Secret Stash, Armed Escort, Stowaways) replace Send for Aid."
  },
  "html.opt_ix_parts": {
    "ko": "익스의 부상과 기술 모듈을 함께 쓸 때 익스를 얼마나 쓸까요?",
    "en": "How much of Rise of Ix does this game use beside the Tech Module?"
  },
  "html.opt_ix_parts_all": {
    "ko": "익스 전부 (공식)",
    "en": "All of Rise of Ix (official)"
  },
  "html.opt_ix_parts_leaders": {
    "ko": "익스 지도자와 기술 타일만 (컴패니언 앱의 조합: 롬버 버니우스 대공·헌드로 모리타니 자작을 뺀 지도자 4종, 기술 타일 16장을 익스 대사관 판에)",
    "en": "Only Rise of Ix's Leaders and Tech tiles (the companion app's mix: four Leaders, not Prince Rhombur Vernius or Viscount Hundro Moritani, and 16 Tech tiles on the Ixian Embassy)"
  },
  "html.opt_ix_parts_tech": {
    "ko": "익스 기술 타일만 (공식: Detonation Devices·Troop Transports를 뺀 16장을 익스 대사관 판에; 아라킨 스카웃과는 함께 쓰지 않음)",
    "en": "Only Rise of Ix's Tech tiles (official: 16 of them, not Detonation Devices or Troop Transports, on the Ixian Embassy; not with Arrakeen Scouts)"
  },
  "html.opt_rise_of_ix": {
    "ko": "익스의 부상 확장 (드레드노트·기술 타일·운송 트랙·새 카드·지도자 6종)",
    "en": "Rise of Ix expansion (dreadnoughts · Tech tiles · Shipping track · new cards · 6 Leaders)"
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
    "ko": "내 핸드",
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
    "ko": "검토 플레이어",
    "en": "Review player"
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
    "ko": "한 차례씩",
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
  "html.search_ai_note": {
    "ko": "탐색 AI는 학습한 망으로 몇 수 앞을 두어 보고 고릅니다. 한 결정에 보통 1–3초 걸리고, 생각하는 동안에도 화면은 움직입니다.",
    "en": "The Search AI tries a few moves ahead with its trained network before it picks one. A decision usually takes 1–3 seconds, and the page keeps responding while it thinks."
  },
  "html.seat_assignment_legend": {
    "ko": "플레이어 배정",
    "en": "Player Assignment"
  },
  "html.seats_aria": {
    "ko": "플레이어",
    "en": "Players"
  },
  "html.setup_title": {
    "ko": "새 게임",
    "en": "New Game"
  },
  "html.split_actions_aria": {
    "ko": "행동 열 너비",
    "en": "Actions column width"
  },
  "html.split_market_aria": {
    "ko": "공용 카드 열 너비",
    "en": "Shared cards column width"
  },
  "html.split_seats_aria": {
    "ko": "플레이어 열 너비",
    "en": "Players column width"
  },
  "html.split_title": {
    "ko": "열 너비 조절 (두 번 클릭: 기본값)",
    "en": "Resize the column (double-click: default width)"
  },
  "layout.hand_order_reset": {
    "ko": "순서 되돌리기",
    "en": "Reset order"
  },
  "layout.hand_order_reset_title": {
    "ko": "이 브라우저에서 바꾼 카드 순서를 지우고 원래 순서로 되돌립니다",
    "en": "Forget the card order set in this browser and show the original order"
  },
  "panels.agent_remaining": {
    "ko": "남은 {agent}",
    "en": "{agent} remaining"
  },
  "panels.battle_label": {
    "ko": "배틀 아이콘",
    "en": "Battle icons"
  },
  "panels.chairdog_return": {
    "ko": "의자개: {reveal_turn} 시작 때 {hand}로 {{cards}}",
    "en": "Chairdog: returns to {hand} at the start of {reveal_turn} — {{cards}}"
  },
  "panels.contracts_label": {
    "ko": "{contract}",
    "en": "Contracts"
  },
  "panels.deck_top_badge": {
    "ko": "카드덱 맨 위",
    "en": "Top of deck"
  },
  "panels.deck_top_put_back": {
    "ko": "{deck} 맨 위 카드({{card}}) 그대로 두기",
    "en": "Leave top card of {deck} ({{card}}) on top"
  },
  "panels.deck_top_discard": {
    "ko": "{deck} 맨 위 카드({{card}}) 버리기",
    "en": "Discard top card of {deck} ({{card}})"
  },
  "panels.deck_top_draw": {
    "ko": "{solari} 1 지불 → {deck} 맨 위 카드({{card}}) 뽑기",
    "en": "Pay 1 {solari} -> Draw top card of {deck} ({{card}})"
  },
  "panels.deck_top_draw_free": {
    "ko": "{deck} 맨 위 카드({{card}}) 뽑기",
    "en": "Draw top card of {deck} ({{card}})"
  },
  "panels.deck_top_trash": {
    "ko": "{deck} 맨 위 카드({{card}}) 폐기",
    "en": "Trash top card of {deck} ({{card}})"
  },
  "panels.deck_list_note": {
    "ko": "이름순으로 보여 줍니다. 뽑는 순서와는 무관합니다.",
    "en": "Shown by name, not in draw order."
  },
  "panels.deck_view": {
    "ko": "{deck} 구성 보기 (순서 비공개)",
    "en": "View {deck} contents (order hidden)"
  },
  "panels.deck_view_top": {
    "ko": "{deck} 구성 보기 (순서 비공개, 맨 위 카드 표시)",
    "en": "View {deck} contents (order hidden, top card marked)"
  },
  "panels.deck_list_top_badge": {
    "ko": "맨 위",
    "en": "Top"
  },
  "panels.deck_list_top_title": {
    "ko": "{deck} 맨 위 카드",
    "en": "top card of the {deck}"
  },
  "panels.deck_list_top_note": {
    "ko": "맨 위로 표시한 카드는 {{source}} 효과로 확인한 {deck} 맨 위 카드입니다.",
    "en": "The card marked Top is the top card of the {deck}, seen through {{source}}."
  },
  "panels.deck_list_public_top_note": {
    "ko": "맨 위로 표시한 카드는 앞면으로 {deck} 맨 위에 놓아 모두가 아는 카드입니다.",
    "en": "The card marked Top was put face up on top of the {deck}, so everyone knows it."
  },
  "panels.my_deck": {
    "ko": "내 {deck} · {{count}}장 (순서 비공개)",
    "en": "My deck · {{count}} cards (order hidden)"
  },
  "panels.seat_deck": {
    "ko": "{{seat}}의 {deck} · {{count}}장 (순서 비공개)",
    "en": "{{seat}}'s deck · {{count}} cards (order hidden)"
  },
  "panels.my_deck_pool": {
    "ko": "내 {deck}·{hand}에 있는 카드 · {{count}}장",
    "en": "In my deck or hand · {{count}} cards"
  },
  "panels.seat_deck_pool": {
    "ko": "{{seat}}의 {deck}·{hand}에 있는 카드 · {{count}}장",
    "en": "In {{seat}}'s deck or hand · {{count}} cards"
  },
  "panels.deck_pool_note": {
    "ko": "어느 카드가 {deck}에 있고 어느 카드가 {hand}에 있는지는 알 수 없습니다. 획득한 카드·버린 카드·폐기한 카드가 모두 공개되므로 누구나 셀 수 있는 목록입니다.",
    "en": "Which of these are in the deck and which in the hand is not known. Every card bought, discarded or trashed is public, so anyone can count this list."
  },
  "panels.seat_piles_view": {
    "ko": "{deck}·{hand}와 {discard_pile} 보기",
    "en": "View the deck, hand and discard pile"
  },
  "panels.discard_pile_view": {
    "ko": "{discard_pile} 보기",
    "en": "View {discard_pile}"
  },
  "panels.face_down_badge": {
    "ko": "뒷면",
    "en": "Face down"
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
    "ko": "핸드에 카드 없음",
    "en": "No cards in hand"
  },
  "panels.hand_public_label": {
    "ko": "{hand} (공개) ",
    "en": "Hand (public) "
  },
  "panels.deck_public_top_label": {
    "ko": "{deck} 맨 위 (공개) ",
    "en": "Top of deck (public) "
  },
  "panels.in_play_label": {
    "ko": "플레이 영역",
    "en": "In play"
  },
  "panels.this_turn_badge": {
    "ko": "이번 차례",
    "en": "This turn"
  },
  "panels.this_turn_title": {
    "ko": "이번 차례에 낸 카드",
    "en": "Played this turn"
  },
  "panels.this_turn_pending_title": {
    "ko": "에이전트 칸이 아직 남아 있음 — 다른 효과로 폐기하면 에이전트 칸의 남은 효과는 사라집니다",
    "en": "Agent box still pending — trashing it by another effect loses the rest of its Agent box"
  },
  "panels.intrigue_deck_top_badge": {
    "ko": "책략 카드덱 맨 위",
    "en": "Top of Intrigue deck"
  },
  "panels.intrigue_faceup_label": {
    "ko": "공개 대기 {intrigue_card} ",
    "en": "Face-up Intrigue "
  },
  "panels.intrigue_resolving_label": {
    "ko": "{intrigue_card} 해결 중 ",
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
  "panels.swordmaster": {
    "ko": "소드마스터",
    "en": "Swordmaster"
  },
  "panels.mentat_at": {
    "ko": "멘타트: {{where}}",
    "en": "Mentat: {{where}}"
  },
  "panels.garrison_troops": {
    "ko": "{garrison}의 {troop}",
    "en": "{troop}s in the {garrison}"
  },
  "panels.conflict_troops": {
    "ko": "{conflict}의 {troop}",
    "en": "{troop}s in the {conflict}"
  },
  "panels.mentat_next_round": {
    "ko": "다음 라운드에 멘타트",
    "en": "the Mentat next round"
  },
  "panels.voice_blocked": {
    "ko": "{{card}}: 다음 {agent}는 {{spaces}} 불가",
    "en": "{{card}}: next {agent} not to {{spaces}}"
  },
  "panels.infiltrate_turn": {
    "ko": "{{card}}: 이번 차례 다른 플레이어의 {agent}가 막지 않음",
    "en": "{{card}}: other players' {agent}s do not block this turn"
  },
  "panels.deck_top_round": {
    "ko": "{{card}}: 이번 라운드 획득한 카드를 {deck} 맨 위에 놓을 수 있음",
    "en": "{{card}}: cards acquired this round may go on top of the {deck}"
  },
  "panels.masterstroke_name": {
    "ko": "절묘한 수완",
    "en": "Masterstroke"
  },
  "panels.masterstroke_secret": {
    "ko": "{{ability}}: 비밀 팩션 둘",
    "en": "{{ability}}: two secret Factions"
  },
  "panels.dreadnought_supply": {
    "ko": "개인 공급처의 드레드노트 {{count}}",
    "en": "Dreadnoughts in supply {{count}}"
  },
  "panels.freighter_step": {
    "ko": "화물선: 운송 트랙 {{step}}칸",
    "en": "Freighter: Shipping track step {{step}}"
  },
  "panels.negotiators": {
    "ko": "익스 게임판의 협상가 {{count}}",
    "en": "Negotiators on the Ix board {{count}}"
  },
  "panels.snoopers": {
    "ko": "탐지기 토큰: {{factions}}",
    "en": "Snooper tokens: {{factions}}"
  },
  "panels.set_aside_own": {
    "ko": "따로 둔 카드: {{card}} (나만 봄)",
    "en": "Set aside: {{card}} (only you see this)"
  },
  "panels.set_aside_hidden": {
    "ko": "따로 둔 카드 1장",
    "en": "One card set aside"
  },
  "panels.set_aside_returned": {
    "ko": "따로 둔 카드를 이번 차례에 돌려받음",
    "en": "The set-aside card came back this turn"
  },
  "panels.strategic_push": {
    "ko": "Strategic Push: 이번 교전에서 승리하면 솔라리 {{solari}}",
    "en": "Strategic Push: {{solari}} Solari if this seat wins this Conflict"
  },
  "panels.starting_contract_pair": {
    "ko": "받은 시작 {contract} 후보: {{names}} (나만 봄)",
    "en": "Starting {contract} choices given: {{names}} (only you see this)"
  },
  "panels.starting_contract_picked": {
    "ko": "고른 시작 {contract}: {{name}} (모두 고르면 공개, 나만 봄)",
    "en": "Starting {contract} chosen: {{name}} (revealed once all have chosen; only you see this)"
  },
  "panels.known_intrigue_held": {
    "ko": "이 플레이어가 쥔 것으로 아는 책략 카드: {{cards}} (나만 봄)",
    "en": "Intrigue cards you know this player holds: {{cards}} (only you see this)"
  },
  "panels.ix_pending_shipping": {
    "ko": "아직 받을 운송 보상: {{steps}}칸",
    "en": "Shipping rewards still to take: track spaces {{steps}}"
  },
  "panels.ix_pending_tech": {
    "ko": "기술 획득: 기술 할인 {{discount}} · {{payment}}로 지불 · 돌려놓을 수 있는 협상가 {{negotiators}}",
    "en": "Acquire Tech: Tech Discount {{discount}} · paid in {{payment}} · Negotiators you may return {{negotiators}}"
  },
  "panels.masterstroke_own": {
    "ko": "{{ability}}: {{factions}} (나만 봄)",
    "en": "{{ability}}: {{factions}} (only you see this)"
  },
  "panels.masterstroke_revealed": {
    "ko": "{{ability}}: {{factions}} 공개",
    "en": "{{ability}}: {{factions}} revealed"
  },
  "panels.mentat_on_leader": {
    "ko": "지도자 위",
    "en": "on the Leader"
  },
  "panels.family_atomics": {
    "ko": "가문 핵 토큰",
    "en": "Family Atomics"
  },
  "panels.my_discard": {
    "ko": "내 {discard_pile}",
    "en": "My discard pile"
  },
  "panels.my_hand_public": {
    "ko": "내 {hand}의 공개된 카드 ({{count}})",
    "en": "Public cards in my hand ({{count}})"
  },
  "panels.seat_hand_public": {
    "ko": "{{seat}} {hand}의 공개된 카드 ({{count}})",
    "en": "Public cards in {{seat}}'s hand ({{count}})"
  },
  "panels.seat_discard": {
    "ko": "{{seat}}의 {discard_pile}",
    "en": "{{seat}}'s discard pile"
  },
  "panels.my_hand": {
    "ko": "내 핸드 · {{seat}}",
    "en": "My hand · {{seat}}"
  },
  "panels.navigation_progress": {
    "ko": "{navigation} {{played}}장 사용, {{remaining}}장 남음",
    "en": "{{played}} Navigation card(s) played, {{remaining}} remaining"
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
  "panels.neutral_leader_ability": {
    "ko": "{leader} 능력",
    "en": "{leader} ability"
  },
  "panels.log_reward_line": {
    "ko": "{{n}}번째 줄",
    "en": "line {{n}}"
  },
  "panels.log_leader_ability_resolved": {
    "ko": "{{ability}}({{leader}})",
    "en": "{{ability}} ({{leader}})"
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
  "panels.pass_fold_conflict_end_intrigue": {
    "ko": "{conflict} 종료 발동 {intrigue_card} 쓰지 않음",
    "en": "{conflict} End Trigger {intrigue_card} Declined"
  },
  "panels.pass_fold_endgame_intrigue": {
    "ko": "{endgame} {intrigue_card} 패스",
    "en": "{endgame} {intrigue_card} Passed"
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
    "ko": "{{name}}의 핸드",
    "en": "{{name}}'s hand"
  },
  "panels.secret_project": {
    "ko": "비밀 프로젝트 (뒷면 {tech_tile})",
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
  "panels.track_spies_owed": {
    "ko": "놓을 {spy} {{count}}",
    "en": "{{count}} {spy} to place"
  },
  "panels.standings_garrison_header": {
    "ko": "{garrison} {troop}",
    "en": "Garrison"
  },
  "panels.scouts_owed": {
    "ko": "받을 몫",
    "en": "To collect"
  },
  "panels.scouts_helix": {
    "ko": "나선",
    "en": "Helix"
  },
  "panels.scouts_heading": {
    "ko": "아라킨 스카웃",
    "en": "Arrakeen Scouts"
  },
  "panels.scouts_subcommittees": {
    "ko": "소위원회",
    "en": "Subcommittees"
  },
  "panels.scouts_open_seat": {
    "ko": "빈 자리",
    "en": "open"
  },
  "panels.scouts_this_round": {
    "ko": "이번 라운드",
    "en": "This round"
  },
  "panels.scouts_earlier": {
    "ko": "지난 항목",
    "en": "Earlier"
  },
  "panels.scouts_round": {
    "ko": "{{round}}라운드",
    "en": "Round {{round}}"
  },
  "panels.scouts_kind_mission": {
    "ko": "임무",
    "en": "Mission"
  },
  "panels.scouts_kind_event": {
    "ko": "이벤트",
    "en": "Event"
  },
  "panels.scouts_kind_auction": {
    "ko": "경매",
    "en": "Auction"
  },
  "panels.scouts_kind_sale": {
    "ko": "판매",
    "en": "Sale"
  },
  "panels.scouts_kind_subcommittee": {
    "ko": "소위원회",
    "en": "Subcommittee"
  },
  "panels.scouts_pieces": {
    "ko": "임무 조각",
    "en": "Mission pieces"
  },
  "panels.scouts_anyone": {
    "ko": "누구나",
    "en": "anyone"
  },
  "panels.scouts_parked": {
    "ko": "세워 둔 병력 {{count}}",
    "en": "{{count}} parked troops"
  },
  "panels.scouts_parked_commander": {
    "ko": "세워 둔 {commander} 1",
    "en": "1 parked {commander}"
  },
  "panels.scouts_parked_dreadnoughts": {
    "ko": "세워 둔 드레드노트 {{count}}",
    "en": "{{count}} parked dreadnought(s)"
  },
  "panels.scouts_parked_one": {
    "ko": "세워 둔 병력 {{count}}",
    "en": "{{count}} parked troop"
  },
  "panels.scouts_face_down": {
    "ko": "뒷면 카드 {{count}}장",
    "en": "{{count}} face-down cards"
  },
  "panels.scouts_face_down_one": {
    "ko": "뒷면 카드 {{count}}장",
    "en": "{{count}} face-down card"
  },
  "panels.scouts_secrets": {
    "ko": "비밀 선택",
    "en": "Secret picks"
  },
  "panels.scouts_secret_waiting": {
    "ko": "아직 비공개: {{round}}라운드 {{name}} — {{seats}}",
    "en": "Not revealed yet: Round {{round}} {{name}} — {{seats}}"
  },
  "panels.scouts_secret_due": {
    "ko": "{{round}}라운드: ",
    "en": "Round {{round}}: "
  },
  "panels.scouts_own_pick": {
    "ko": "내 선택 — {{name}}: ",
    "en": "My pick — {{name}}: "
  },
  "panels.scouts_pick_faction": {
    "ko": "고른 팩션: {{faction}}",
    "en": "Faction named: {{faction}}"
  },
  "panels.scouts_bids": {
    "ko": "입찰 확정: {{seats}}",
    "en": "Bids confirmed: {{seats}}"
  },
  "panels.scouts_no_bids": {
    "ko": "아직 확정한 플레이어 없음",
    "en": "No bid confirmed yet"
  },
  "panels.scouts_own_bid": {
    "ko": "내 입찰액: {{count}}",
    "en": "My bid: {{count}}"
  },
  "panels.scouts_currency": {
    "ko": "입찰 자원:",
    "en": "Bid resource:"
  },
  "panels.scouts_market": {
    "ko": "공개된 카드",
    "en": "Revealed cards"
  },
  "panels.scouts_calls": {
    "ko": "호가: {{calls}}",
    "en": "Calls: {{calls}}"
  },
  "panels.scouts_pass": {
    "ko": "패스",
    "en": "pass"
  },
  "panels.scouts_lost_picks": {
    "ko": "쓰이지 않은 비밀 선택",
    "en": "Secret picks never due"
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
    "ko": "플레이어",
    "en": "Player"
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
  "panels.supply_commander": {
    "ko": "{supply}의 {commander}",
    "en": "{commander} in {supply}"
  },
  "panels.log_reason_acquired": { "ko": "획득", "en": "Acquired" },
  "panels.log_reason_trashed": { "ko": "폐기", "en": "Trashed" },
  "panels.log_reason_discarded": { "ko": "버리기", "en": "Discarded" },
  "panels.log_reason_flipped": { "ko": "뒤집기", "en": "Flipped" },
  "panels.log_reason_grafted": { "ko": "접합", "en": "Grafted" },
  "panels.log_reason_completed": { "ko": "완수", "en": "Completed" },
  "panels.log_reason_used": { "ko": "사용", "en": "Used" },
  "panels.log_cards_more": { "ko": "+{{count}}장", "en": "+{{count}} more" },
  "panels.seat_details_open": { "ko": "자세히 ▸", "en": "Details ▸" },
  "panels.seat_details_title": {
    "ko": "자세히 보기: 이긴 교전 카드, 완수한 {contract}, 폐기한 카드와 타일",
    "en": "Details: won Conflict cards, completed Contracts, trashed cards and tiles"
  },
  "panels.seat_details_viewer": { "ko": "{{name}} 자세히", "en": "{{name}}: details" },
  "panels.details_battle": {
    "ko": "목적 카드와 이긴 교전 카드 ({{count}})",
    "en": "Objective and won Conflict cards ({{count}})"
  },
  "panels.details_contracts": {
    "ko": "완수한 {contract} ({{count}})",
    "en": "Completed Contracts ({{count}})"
  },
  "panels.details_trashed_cards": { "ko": "폐기한 카드 ({{count}})", "en": "Trashed cards ({{count}})" },
  "panels.details_trashed_skills": {
    "ko": "폐기한 {commander_skill} ({{count}})",
    "en": "Trashed Sardaukar Commander Skills ({{count}})"
  },
  "panels.details_trashed_tech": {
    "ko": "폐기한 {tech_tile} ({{count}})",
    "en": "Trashed Tech tiles ({{count}})"
  },
  "panels.details_none": { "ko": "없음", "en": "None" },
  "panels.battle_card_matched": { "ko": "뒤집힘", "en": "Face down" },
  "panels.memories_title": {
    "ko": "기억: 스파이스의 고통으로 게임판의 베네 게세리트 영역에 옮긴 병력",
    "en": "Memories: troops Spice Agony moved to the Bene Gesserit board area"
  },
  "panels.tactics_space": {
    "ko": "전술 트랙 {{space}}칸",
    "en": "Tactics space {{space}}"
  },
  "panels.feyd_track_space": {
    "ko": "훈련 트랙: {{space}}",
    "en": "Training track: {{space}}"
  },
  "panels.tech_label": {
    "ko": "{tech_tile}",
    "en": "Tech"
  },
  "panels.thinking": {
    "ko": "생각 중…",
    "en": "Thinking…"
  },
  "panels.ai_plays_badge": {
    "ko": "AI가 둠",
    "en": "AI plays"
  },
  "panels.ai_plays_title": {
    "ko": "{{name}}의 자리 · {{kind}}이(가) 대신 두는 중",
    "en": "{{name}}'s seat · {{kind}} is playing it"
  },
  "panels.hand_to_ai_button": {
    "ko": "AI에게 맡기기",
    "en": "Let the AI play"
  },
  "panels.take_back_button": {
    "ko": "직접 두기",
    "en": "Play myself"
  },
  "panels.seat_change_to_ai": {
    "ko": "🤖 {{name}} 자리를 AI가 맡음",
    "en": "🤖 The AI now plays {{name}}"
  },
  "panels.seat_change_to_human": {
    "ko": "↩ {{name}} 자리를 다시 사람이 둠",
    "en": "↩ {{name}} is played by its person again"
  },
  "panels.twisted_deck": {
    "ko": "뒤틀린 책략 카드덱 {{count}}",
    "en": "Twisted Intrigue deck {{count}}"
  },
  "panels.undo_row": {
    "ko": "↩ 플레이어{{seat}}이(가) {{count}}단계 되돌림",
    "en": "↩ Player {{seat}} undid {{count}} step(s)"
  },
  "panels.undone_suffix": {
    "ko": " (되돌림)",
    "en": " (undone)"
  },
  "panels.usurp_trash": {
    "ko": "찬탈: 차례 끝에 {{card}} 폐기",
    "en": "Usurp: Trash {{card}} at end of turn"
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
    "ko": "획득한 카드: ",
    "en": "Cards acquired: "
  },
  "render.buyable_cards_heading": {
    "ko": "획득할 수 있는 카드 — 테이블에서 빛나는 카드를 눌러도 됩니다",
    "en": "Cards you can acquire — you can also click the highlighted cards on the table"
  },
  "render.combat_result_line": {
    "ko": "{{name}} — {{ranks}} — 내 보상: {{reward}}",
    "en": "{{name}} — {{ranks}} — Your reward: {{reward}}"
  },
  "render.combat_result_line_ranks": {
    "ko": "{{name}} — {{ranks}}",
    "en": "{{name}} — {{ranks}}"
  },
  "render.combat_result_rank_1": {
    "ko": "1등",
    "en": "1st"
  },
  "render.combat_result_rank_2": {
    "ko": "2등",
    "en": "2nd"
  },
  "render.combat_result_rank_3": {
    "ko": "3등",
    "en": "3rd"
  },
  "render.combat_result_unranked": {
    "ko": "없음 (순위 밖)",
    "en": "none (not ranked)"
  },
  "render.confirm_count_label": {
    "ko": "{{count}}개 {{label}}",
    "en": "{{count}} {{label}}"
  },
  "render.confirm_short": {
    "ko": "확정",
    "en": "Confirm"
  },
  "render.turn_end_bid": {
    "ko": "{{resource}} {{count}} 입찰 · 턴 종료 ▶",
    "en": "Bid {{count}} {{resource}} · End turn ▶"
  },
  "render.turn_end_call": {
    "ko": "{{resource}} {{count}} 호가 · 턴 종료 ▶",
    "en": "Call {{count}} {{resource}} · End turn ▶"
  },
  "render.turn_end_pass_call": {
    "ko": "패스 ({{resource}} 0) · 턴 종료 ▶",
    "en": "Pass (0 {{resource}}) · End turn ▶"
  },
  "render.contract_bank": {
    "ko": "남은 계약",
    "en": "Contract bank"
  },
  "render.count_step_down": {
    "ko": "하나 적게",
    "en": "One fewer"
  },
  "render.scouts_called_amounts": {
    "ko": "이미 나온 액수: {{amounts}} (부를 수 없음)",
    "en": "Already called: {{amounts}} (cannot be called again)"
  },
  "render.scouts_highest_call": {
    "ko": "최고 호가: {{amount}} (더 높게만 부를 수 있음)",
    "en": "Highest call: {{amount}} (only a higher call can be made)"
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
    "ko": "종료 후 공개 (모든 비공개 영역)",
    "en": "Post-game disclosure (all private zones)"
  },
  "render.effect_preview_title": {
    "ko": "효과 미리보기",
    "en": "Effect preview"
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
    "ko": "{intrigue_card} ({{count}})",
    "en": "{intrigue_card} ({{count}})"
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
    "ko": "{{vp}} 동점 · 동점 판정 항목도 모두 같아 {reveal_turn}를 더 늦게 마친 플레이어가 승리",
    "en": "{{vp}} tied · every tiebreaker equal too — the player that finished a {reveal_turn} more recently wins"
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
  "render.reveal_choice_optional": {
    "ko": "선택 효과 — 쓰지 않아도 됨, {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
    "en": "Optional — you may leave it; it lapses unused when the {reveal_turn} ends"
  },
  "render.reveal_choice_mandatory": {
    "ko": "꼭 고를 효과 — 고르기 전에는 {reveal_turn}를 끝낼 수 없음",
    "en": "Must be chosen — the {reveal_turn} cannot end before you choose"
  },
  "render.reveal_preview_title": {
    "ko": "지금 핸드를 공개하면 바로 얻는 {persuasion}과 {strength} ({reveal_turn} 중의 선택 효과는 제외)",
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
  "render.badge_ix_tech": {
    "ko": "익스 기술 타일",
    "en": "Ix Tech tiles"
  },
  "render.badge_ix_leaders": {
    "ko": "익스 지도자",
    "en": "Ix Leaders"
  },
  "render.badge_immortality": {
    "ko": "불멸",
    "en": "Immortality"
  },
  "render.badge_go_to_11": {
    "ko": "11점을 향해",
    "en": "Go to 11"
  },
  "render.badge_epic_game": {
    "ko": "에픽 게임 모드",
    "en": "Epic Game Mode"
  },
  "render.badge_imperium_cards": {
    "ko": "원판 카드",
    "en": "original cards"
  },
  "render.badge_scouts": {
    "ko": "아라킨 스카웃",
    "en": "Arrakeen Scouts"
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
    "ko": "플레이어{{seat}} (당신)",
    "en": "Player {{seat}} (you)"
  },
  "render.second_place": {
    "ko": " · 2위 {{name}}",
    "en": " · 2nd place {{name}}"
  },
  "render.shared_deck_order_title": {
    "ko": "공용 카드덱 순서",
    "en": "Shared deck order"
  },
  "scouts_stage.region": {
    "ko": "아라킨 스카웃 카드 · {{kind}} · {{name}}",
    "en": "Arrakeen Scouts card · {{kind}} · {{name}}"
  },
  "scouts_stage.hide": { "ko": "게임판 보기", "en": "Show board" },
  "scouts_stage.hide_title": {
    "ko": "카드를 접고 게임판을 봅니다 (A)",
    "en": "Fold the card away to see the board (A)"
  },
  "scouts_stage.show": { "ko": "카드로 보기", "en": "Show card" },
  "scouts_stage.show_more": {
    "ko": "{{name}} 외 {{more}}",
    "en": "{{name}} +{{more}}"
  },
  "scouts_stage.show_title": {
    "ko": "아라킨 스카웃 카드를 게임판 위에 펼칩니다 (A)",
    "en": "Bring the Arrakeen Scouts card up over the board (A)"
  },
  "scouts_stage.fold": { "ko": "카드 접기", "en": "Hide card" },
  "scouts_stage.fold_title": {
    "ko": "게임판 위 아라킨 스카웃 카드를 접습니다 (A)",
    "en": "Fold the Arrakeen Scouts card over the board away (A)"
  },
  "scouts_stage.prev": { "ko": "◀ 이전", "en": "◀ Previous" },
  "scouts_stage.next": { "ko": "다음 ▶", "en": "Next ▶" },
  "scouts_stage.prev_aria": {
    "ko": "이번 라운드의 이전 스카웃 항목",
    "en": "This round's previous Scouts item"
  },
  "scouts_stage.next_aria": {
    "ko": "이번 라운드의 다음 스카웃 항목",
    "en": "This round's next Scouts item"
  },
  "scouts_stage.prev_title": {
    "ko": "이전 항목 (카드 안에서 ←)",
    "en": "Previous item (← inside the card)"
  },
  "scouts_stage.next_title": {
    "ko": "다음 항목 (카드 안에서 →)",
    "en": "Next item (→ inside the card)"
  },
  "scouts_stage.new": { "ko": "새", "en": "New" },
  "scouts_stage.with_new": {
    "ko": "{{label}} · 아직 안 본 항목이 있습니다",
    "en": "{{label}} · an item you have not seen yet"
  },
  "scouts_stage.count": {
    "ko": "{{index}} / {{total}}",
    "en": "{{index}} / {{total}}"
  },
  "scouts_stage.secrets_name": {
    "ko": "비밀 선택 공개",
    "en": "Secret picks revealed"
  },
  "scouts_stage.secrets_pending_name": {
    "ko": "비밀 선택 공개 준비",
    "en": "Secret picks: reveal to come"
  },
  "scouts_stage.secrets_event": {
    "ko": "{{round}}라운드 {{name}}",
    "en": "Round {{round}} {{name}}"
  },
  "render.scouts_decision_item": {
    "ko": "아라킨 스카웃 · {{kind}} · {{name}}",
    "en": "Arrakeen Scouts · {{kind}} · {{name}}"
  },
  "render.scouts_decision_secrets": {
    "ko": "아라킨 스카웃 · 비밀 선택 공개",
    "en": "Arrakeen Scouts · Secret picks revealed"
  },
  "render.scouts_decision_secret_item": {
    "ko": "아라킨 스카웃 · 비밀 선택 공개 · {{name}}",
    "en": "Arrakeen Scouts · Secret picks revealed · {{name}}"
  },
  "render.scouts_joined_by": {
    "ko": "{{player}} 가입",
    "en": "Joined by {{player}}"
  },
  "render.scouts_line_unavailable": {
    "ko": "지금은 고를 수 없음",
    "en": "Not available now"
  },
  "render.scouts_line_unavailable_title": {
    "ko": "지금은 고를 수 없는 선택지입니다. 할 수 있게 되면 바로 고를 수 있습니다",
    "en": "You cannot take this line right now; it opens as soon as you can"
  },
  "render.shortfall_contract": {
    "ko": "{contract} 아이콘 {{requested}}개 소멸 — 가져갈 수 있는 {contract} 없음",
    "en": "{{requested}} {contract} icon(s) fizzle: no {contract} you can take"
  },
  "render.shortfall_intrigue": {
    "ko": "책략 카드덱과 {discard_pile}를 합쳐도 {{short}}장 모자람",
    "en": "Intrigue deck and {discard_pile} are {{short}} short of the draw"
  },
  "render.shortfall_intrigue_twisted": {
    "ko": "책략 카드덱과 {discard_pile}를 합쳐도 {{short}}장 모자람 ({discard_pile}의 뒤틀린 책략 {{twisted}}장은 섞지 않음)",
    "en": "Intrigue deck and {discard_pile} are {{short}} short of the draw (not counting {{twisted}} Twisted Intrigue there, which are never reshuffled)"
  },
  "render.shortfall_no_effect": {
    "ko": "지금 내면 아무 효과가 없음",
    "en": "Playing it now has no effect"
  },
  "render.shortfall_specimens": {
    "ko": "{supply} 부족: {specimen} {{requested}}개 중 {{made}}개만 생성",
    "en": "Short {supply}: only {{made}} of {{requested}} {specimen} made"
  },
  "render.shortfall_suspensor": {
    "ko": "{{tile}}: {troop} {{requested}}개 중 {{made}}개만 배치",
    "en": "{{tile}}: only {{made}} of {{requested}} {troop} deployed"
  },
  "render.shortfall_title": {
    "ko": "선택은 할 수 있지만 인쇄된 만큼 되지 않습니다",
    "en": "You can still choose, but it does less than printed"
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
  "render.subcommittee_preview_join": {
    "ko": "이 원로회 자리로 가입할 수 있는 소위원회: {{names}}",
    "en": "Subcommittees this seat lets you join: {{names}}"
  },
  "render.subcommittee_preview_later": {
    "ko": "지금 바로 가입할 수 있는 소위원회는 없습니다. 이번 차례 안에 조건을 갖추면 가입할 수 있습니다",
    "en": "No subcommittee you can join right away; you may still join one later this turn"
  },
  "render.subcommittee_preview_none": {
    "ko": "이 원로회 자리로 가입할 수 있는 빈 소위원회가 없습니다",
    "en": "No open subcommittee is left for this seat to join"
  },
  "render.subcommittee_preview_not_now": {
    "ko": "지금은 불가: {{lines}}",
    "en": "Not now: {{lines}}"
  },
  "render.turn_end_button": {
    "ko": "턴 종료 ▶",
    "en": "End turn ▶"
  },
  "render.turn_end_button_pass": {
    "ko": "패스 · 턴 종료 ▶",
    "en": "Pass · End turn ▶"
  },
  "render.turn_end_button_decline": {
    "ko": "쓰지 않음 · 턴 종료 ▶",
    "en": "Decline · End turn ▶"
  },
  "render.turn_end_button_finish": {
    "ko": "끝내기 · 턴 종료 ▶",
    "en": "Finish · End turn ▶"
  },
  "render.turn_end_button_nothing": {
    "ko": "할 수 있는 선택 없음 · 턴 종료 ▶",
    "en": "Nothing to take · End turn ▶"
  },
  "render.turn_end_button_no_influence": {
    "ko": "잃을 영향력 없음 · 턴 종료 ▶",
    "en": "No Influence to lose · End turn ▶"
  },
  "render.turn_end_button_with_buys": {
    "ko": "획득 끝 · 턴 종료 ▶",
    "en": "Done acquiring · End turn ▶"
  },
  "render.thinking_decision": {
    "ko": "{{name}} 생각 중…",
    "en": "{{name}} is thinking…"
  },
  "render.ai_plays_own_seat": {
    "ko": "AI가 {{name}} 자리를 대신 두는 중입니다. 다시 두려면 자리의 '직접 두기'를 누르세요.",
    "en": "The AI is playing {{name}}. Press 'Play myself' on the seat to take it back."
  },
  "render.held_choice_hint": {
    "ko": "보내면 되돌릴 수 없는 선택입니다. \"확정 ▶\"을 눌러야 보내지고, 그 전에는 다른 것을 고르거나 목록에서 한 번 더 눌러(또는 Esc) 취소할 수 있습니다.",
    "en": "This choice cannot be taken back once sent. It is sent only with \"Confirm ▶\"; until then you can pick another one, or click it again in the list (or press Esc) to cancel."
  },
  "render.held_send_button": {
    "ko": "확정 ▶",
    "en": "Confirm ▶"
  },
  "render.turn_end_prompt": {
    "ko": "이번 차례에 할 일을 마쳤습니다.",
    "en": "You have nothing left to do this turn."
  },
  "render.unavailable_acquire_heading": {
    "ko": "지금은 획득할 수 없는 카드",
    "en": "Cards you cannot acquire now"
  },
  "render.unavailable_choice_heading": {
    "ko": "지금 고를 수 없는 선택지",
    "en": "Choices you cannot take now"
  },
  "render.unavailable_intrigue_heading": {
    "ko": "지금은 쓸 수 없는 책략 카드",
    "en": "Intrigue cards you cannot play now"
  },
  "render.unavailable_title": {
    "ko": "지금은 고를 수 없습니다. 할 수 있게 되면 바로 고를 수 있습니다",
    "en": "You cannot take this right now; it opens as soon as you can"
  },
  "render.unavailable_waiting_heading": {
    "ko": "조건을 기다리는 효과",
    "en": "Effects waiting on their condition"
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
  "render.waiting_decision": {
    "ko": "{{name}} 결정 대기 중…",
    "en": "Waiting for {{name}}'s decision…"
  },
  "render.waiting_hint_empty": {
    "ko": " (아직 참여하지 않은 플레이어입니다 — 방 링크를 보내 주세요)",
    "en": " (this player hasn't joined yet — send the room link)"
  },
  "render.waiting_hint_offline": {
    "ko": " (접속이 끊겨 있습니다)",
    "en": " (disconnected)"
  },
  "render.waiting_turn_end": {
    "ko": "{{name}}의 턴 종료를 기다리는 중…",
    "en": "Waiting for {{name}} to end the turn…"
  },
  "render.zone_heading": {
    "ko": "{{zone}} · {{count}}",
    "en": "{{zone}} · {{count}}"
  },
  "render.agent_box_heading": {
    "ko": "{{name}} — {agent_box}",
    "en": "{{name}} — {agent_box}"
  },
  "render.agent_box_locked": {
    "ko": "다른 칸의 선택을 마친 뒤 해결할 수 있음",
    "en": "Available after the other box's choice"
  },
  "render.agent_box_others_heading": {
    "ko": "그 밖의 선택",
    "en": "Other choices"
  },
  "render.turn_card_suffix": {
    "ko": "이번 차례에 낸 카드",
    "en": "card played this turn"
  },
  "render.forfeit_agent": {
    "ko": "⚠ 아직 쓰지 않은 에이전트 칸 효과를 잃습니다 — {{card}}",
    "en": "⚠ Loses the unused Agent box effects of {{card}}"
  },
  "render.forfeit_reveal": {
    "ko": "⚠ 아직 쓰지 않은 공개 칸 효과를 잃습니다 — {{card}}",
    "en": "⚠ Loses the unused Reveal effect of {{card}}"
  },
  "render.turn_end_lapses": {
    "ko": "⚠ 차례를 끝내면 쓰지 않은 효과가 사라집니다:",
    "en": "⚠ Ending the turn drops these unused effects:"
  },
  "render.lapse_agent_box": {
    "ko": "에이전트 칸",
    "en": "Agent box"
  },
  "render.turn_end_persuasion": {
    "ko": "⚠ 남은 {persuasion} {{left}} — 획득할 수 있는 카드 {{buys}}장",
    "en": "⚠ {{left}} {persuasion} left — {{buys}} cards you can acquire"
  },
  "render.reveal_turn_agents_left": {
    "ko": "⚠ 에이전트 {{count}} 남음 — 공개 차례를 하면 이번 라운드에는 보낼 수 없습니다",
    "en": "⚠ {{count}} Agents left — a Reveal turn ends your Agent turns this round"
  },
  "render.turn_end_deploy": {
    "ko": "⚠ 주둔지에 남음: {{units}}",
    "en": "⚠ Stays in your garrison: {{units}}"
  },
  "render.forfeit_title": {
    "ko": "이미 폐기된 카드의 효과는 받거나 쓸 수 없습니다. 그 카드의 효과를 먼저 쓰면 잃지 않습니다.",
    "en": "You can't receive or activate an effect from a card that is already trashed. Use that card's effects first to keep them."
  },
  "render.earlier_turn_card_suffix": {
    "ko": "앞 차례에 낸 카드",
    "en": "card played on an earlier turn"
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
    "ko": "{intrigue_card} {discard_pile} 섞기",
    "en": "{intrigue_card} {discard_pile} shuffled"
  },
  "core.chance_secrets_steal": {
    "ko": "{{thief}}, {{victim}}에게서 {steal_intrigue}",
    "en": "{{thief}}: {steal_intrigue} from {{victim}}"
  },
  "core.chance_other": {
    "ko": "기타",
    "en": "other"
  },
  "core.chance_scouts": {
    "ko": "아라킨 스카웃 추첨({{what}})",
    "en": "Arrakeen Scouts draw ({{what}})"
  },
  "core.chance_scouts_layout": {
    "ko": "임무 라운드",
    "en": "Mission rounds"
  },
  "core.chance_scouts_auction_round": {
    "ko": "경매 라운드",
    "en": "Auction round"
  },
  "core.pause_step": {
    "ko": "공개 전 멈춤 (앞 좌석이 되돌릴 수 있던 자리)",
    "en": "Pause before a reveal (where the last choice could be taken back)"
  },
  "core.chance_scouts_contracts": {
    "ko": "앞면 {contract} 교체",
    "en": "Face-up {contract} replacement"
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
    "ko": "이 플레이어",
    "en": "This player's"
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
    "ko": "플레이어{{seat}} ({{kind}})",
    "en": "Player {{seat}} ({{kind}})"
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
    "ko": "플레이어{{seat}}: {{action}}",
    "en": "Player {{seat}}: {{action}}"
  },
  "review.undo_marker": {
    "ko": " · ↩ 플레이어{{seat}}: 여기서 {{count}}단계 되돌림: ",
    "en": " · ↩ Player {{seat}}: rewound {{count}} step(s) here: "
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
  "screens.delete_confirm_button": {
    "ko": "정말 삭제?",
    "en": "Delete for good?"
  },
  "screens.empty_seat": {
    "ko": "참여 가능",
    "en": "Available"
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
    "ko": "참여 종료",
    "en": "Stop playing"
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
    "ko": "내 플레이어",
    "en": "My player"
  },
  "screens.name_required": {
    "ko": "이름을 먼저 적어 주세요.",
    "en": "Enter your name first."
  },
  "screens.no_free_seats": {
    "ko": "모든 플레이어가 참여 중입니다. 호스트에게 자리를 비워 달라고 하세요.",
    "en": "All players have joined. Ask the host to make room."
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
    "ko": "플레이어{{seat}} ({{name}})",
    "en": "Player {{seat}} ({{name}})"
  },
  "screens.refresh_list_button": {
    "ko": "목록 새로 고침",
    "en": "Refresh list"
  },
  "screens.release_seat_failed": {
    "ko": "플레이어 해제 실패 ({{message}})",
    "en": "Couldn't release the player ({{message}})"
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
    "ko": "저장 — 차례가 넘어갈 때마다 자동 저장됩니다",
    "en": "Saves — autosaved every turn"
  },
  "screens.saves_heading_manual": {
    "ko": "저장 — 자동 저장이 꺼져 있습니다",
    "en": "Saves — autosave is off"
  },
  "screens.seat_left": {
    "ko": "참여를 종료했습니다. 다시 참여하려면 플레이어를 고르세요.",
    "en": "You stopped playing. Choose a player to join again."
  },
  "screens.seat_taken": {
    "ko": "방금 다른 사람이 그 플레이어로 참여했습니다.",
    "en": "Someone else just joined as that player."
  },
  "screens.server_address_label": {
    "ko": "친구들이 접속하는 서버 주소 (예: http://100.x.y.z:8000)",
    "en": "Server address your friends connect to (e.g. http://100.x.y.z:8000)"
  },
  "screens.waiting_room_title": {
    "ko": "게임 대기실",
    "en": "Waiting room"
  },
  "screens.waiting_room_status": {
    "ko": "참여 {{joined}}/{{total}}명",
    "en": "{{joined}} of {{total}} joined"
  },
  "screens.waiting_room_me": {
    "ko": "나",
    "en": "Me"
  },
  "screens.waiting_room_note": {
    "ko": "모두 참여하면 \"게임 시작\"이 나타납니다. 자리(차례 순서·색)는 시작할 때 무작위로 정해집니다.",
    "en": "\"Start game\" appears once everyone has joined. The seats (turn order and colour) are drawn at random at the start."
  },
  "screens.waiting_room_ready_note": {
    "ko": "모두 모였습니다. 참여한 사람 누구나 시작할 수 있고, 시작하면 자리를 무작위로 정합니다.",
    "en": "Everyone is here. Anyone who joined may start; the seats are drawn at random then."
  },
  "screens.start_game_button": {
    "ko": "게임 시작 ▶",
    "en": "Start game ▶"
  },
  "screens.sit_button": {
    "ko": "참여",
    "en": "Join"
  },
  "screens.sit_failed": {
    "ko": "참여 실패 ({{message}})",
    "en": "Couldn't join ({{message}})"
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
  "session.ai_pace_failed": {
    "ko": "AI 진행 속도를 바꾸지 못했습니다 ({{message}})",
    "en": "Could not change the AI pace ({{message}})"
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
  "session.hand_to_ai_confirm": {
    "ko": "{{name}} 자리를 AI에게 맡길까요?\n지금까지 둔 수는 더 되돌릴 수 없고, 턴 종료를 기다리던 중이면 차례를 끝낸 것으로 칩니다.\n자리의 '직접 두기'로 언제든 다시 둘 수 있습니다.",
    "en": "Let the AI play {{name}}?\nWhat you played so far can no longer be taken back, and a turn end waiting for your press counts as pressed.\nPress 'Play myself' on the seat to take it back at any time."
  },
  "session.hand_to_ai_failed": {
    "ko": "AI에게 맡기지 못함 ({{message}})",
    "en": "Could not hand the seat to the AI ({{message}})"
  },
  "session.take_back_failed": {
    "ko": "자리를 되찾지 못함 ({{message}})",
    "en": "Could not take the seat back ({{message}})"
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
  "turn.agent_from": {
    "ko": "{{place}}에 있던 {agent}",
    "en": "{agent} from {{place}}"
  },
  "turn.agent_from_unsent": {
    "ko": "아직 보내지 않은 {agent}",
    "en": "An {agent} not yet sent"
  },
  "turn.partner_discount": {
    "ko": "짝 {{names}}: {spice} {{amount}} 할인",
    "en": "Partner {{names}}: {spice} {{amount}} off"
  },
  "turn.partner_discount_none": {
    "ko": "짝 {{names}}: 할인 없음",
    "en": "Partner {{names}}: no discount"
  },
  "turn.partner_unnamed": {
    "ko": "다음에 고를 카드",
    "en": "the card chosen next"
  },
  "turn.graft_solo": {
    "ko": "이 카드만",
    "en": "This card only"
  },
  "turn.hint_both_picked": {
    "ko": "두 카드로 갈 수 있는 장소가 빛납니다. 보낼 곳을 누르세요. (Esc: 취소)",
    "en": "Spaces that fit both cards are highlighted. Click where to send them. (Esc: cancel)"
  },
  "turn.hint_choose_card": {
    "ko": "빛나는 카드 중에서 그 장소에 낼 카드를 누르세요. (Esc: 취소)",
    "en": "Click one of the highlighted cards to play there. (Esc: cancel)"
  },
  "turn.hint_choose_space": {
    "ko": "빛나는 장소 중에서 {agent}를 보낼 곳을 누르세요. (Esc: 취소)",
    "en": "Click a highlighted space to send your {agent} there. (Esc: cancel)"
  },
  "turn.hint_graft_optional": {
    "ko": "빛나는 장소를 누르세요. {graft}으로 함께 낼 카드가 있으면 ＋ 표시된 카드를 먼저 누르세요. (Esc: 취소)",
    "en": "Click a highlighted space. If a card can join by {graft}, click the one marked ＋ first. (Esc: cancel)"
  },
  "turn.hint_graft_required": {
    "ko": "{graft} 카드는 혼자 낼 수 없습니다. ＋ 표시된 카드를 눌러 함께 낼 카드를 고르거나, 장소를 먼저 눌러도 됩니다.",
    "en": "A {graft} card cannot be played alone. Click a card marked ＋ to choose one to play together, or click a space first."
  },
  "turn.hint_start": {
    "ko": "핸드에서 빛나는 카드를 누르세요. 장소를 먼저 눌러도 됩니다.",
    "en": "Click a highlighted card in your hand. You can also click a space first."
  },
  "turn.multiple_choices": {
    "ko": "{{name}}: 선택지가 {{count}}개입니다. 오른쪽 행동 목록에서 고르세요.",
    "en": "{{name}}: {{count}} choices available. Choose from the action list on the right."
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
    "ko": "{{name}}: 이 장소에서 함께 낼 수 없습니다. 함께 낼 카드를 다시 고르거나 되돌리기를 누르세요.",
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
  "turn.start_window_hint": {
    "ko": "쓰지 않아도 이번 차례에 다른 행동을 하기 전까지는 행동 목록에서 쓸 수 있습니다.",
    "en": "If you keep it, you can still play it from the action list until you take another action this turn."
  },
  "turn.start_window_keep": {
    "ko": "차례 시작 카드 쓰지 않음",
    "en": "Keep the turn-start card"
  },
  "turn.start_window_pick_row": {
    "ko": "{{name}}: 창에 있는 줄을 눌러 사용합니다.",
    "en": "{{name}}: use its row in the window to play it."
  },
  "turn.start_window_prompt": {
    "ko": "차례 시작 카드 사용, 또는 쓰지 않고 차례 시작",
    "en": "Play a turn-start card, or keep it and start your turn"
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
    "ko": "보낼 장소",
    "en": "Space"
  },
  "turn.step_together": {
    "ko": "함께",
    "en": "Together"
  },
  "turn.table_hint": {
    "ko": "테이블에서 빛나는 카드나 장소를 눌러 골라도 됩니다.",
    "en": "You can also click a highlighted card or space on the table."
  },
  "html.open_admin": {
    "ko": "서버 관리",
    "en": "Server admin"
  },
  "admin.title": {
    "ko": "서버 관리",
    "en": "Server admin"
  },
  "admin.back": {
    "ko": "게임 화면으로",
    "en": "Back to the game"
  },
  "admin.refresh": {
    "ko": "새로고침",
    "en": "Refresh"
  },
  "admin.last_refresh": {
    "ko": "마지막 새로고침 {{time}}",
    "en": "Last refreshed {{time}}"
  },
  "admin.server_heading": {
    "ko": "서버",
    "en": "Server"
  },
  "admin.machine_heading": {
    "ko": "기기",
    "en": "Machine"
  },
  "admin.games_heading": {
    "ko": "진행 중인 게임",
    "en": "Games in progress"
  },
  "admin.saves_heading": {
    "ko": "저장본",
    "en": "Saves"
  },
  "admin.log_heading": {
    "ko": "최근 로그",
    "en": "Recent log"
  },
  "admin.none": {
    "ko": "없음",
    "en": "none"
  },
  "admin.on": {
    "ko": "켜짐",
    "en": "on"
  },
  "admin.off": {
    "ko": "꺼짐",
    "en": "off"
  },
  "admin.not_signed_in": {
    "ko": "이 브라우저는 호스트로 로그인되어 있지 않습니다.",
    "en": "This browser is not signed in as the host."
  },
  "admin.how_tailscale": {
    "ko": "호스트의 Tailscale 기기에서 이 페이지를 열거나, 관리자 링크(…/admin#admin=키)로 들어오세요.",
    "en": "Open this page from one of the host's own Tailscale devices, or come in with the admin link (…/admin#admin=key)."
  },
  "admin.how_link": {
    "ko": "관리자 링크(…/admin#admin=키)로 들어오세요.",
    "en": "Come in with the admin link (…/admin#admin=key)."
  },
  "admin.link_invalid": {
    "ko": "관리자 링크가 맞지 않습니다: {{message}}",
    "en": "The admin link was refused: {{message}}"
  },
  "admin.f_commit": {
    "ko": "커밋",
    "en": "Commit"
  },
  "admin.f_codec": {
    "ko": "행동 코덱 버전",
    "en": "Action codec version"
  },
  "admin.f_observation": {
    "ko": "관측 버전",
    "en": "Observation version"
  },
  "admin.f_python": {
    "ko": "Python",
    "en": "Python"
  },
  "admin.f_uptime": {
    "ko": "가동 시간",
    "en": "Uptime"
  },
  "admin.f_started": {
    "ko": "시작 시각",
    "en": "Started at"
  },
  "admin.f_access": {
    "ko": "접속 방식",
    "en": "Access"
  },
  "admin.f_public_url": {
    "ko": "공개 주소",
    "en": "Public address"
  },
  "admin.f_autosave": {
    "ko": "자동 저장",
    "en": "Autosave"
  },
  "admin.f_saves_dir": {
    "ko": "저장 폴더",
    "en": "Saves folder"
  },
  "admin.f_search_ai": {
    "ko": "탐색 AI",
    "en": "Search AI"
  },
  "admin.f_search_ai_imperium": {
    "ko": "원판 탐색 AI",
    "en": "Original-game Search AI"
  },
  "admin.f_search_worlds": {
    "ko": "탐색 AI 세계 수 (0 = 끔)",
    "en": "Search AI worlds (0 = off)"
  },
  "admin.f_ai_pace": {
    "ko": "AI 속도",
    "en": "AI pace"
  },
  "admin.f_seating": {
    "ko": "자리 배치",
    "en": "Seating"
  },
  "admin.f_first_player": {
    "ko": "선 플레이어",
    "en": "First player"
  },
  "admin.f_tailscale": {
    "ko": "Tailscale 계정",
    "en": "Tailscale accounts"
  },
  "admin.access_remote": {
    "ko": "원격 (관리는 호스트만)",
    "en": "remote (host-only management)"
  },
  "admin.seating_random": {
    "ko": "무작위",
    "en": "random"
  },
  "admin.seating_fixed": {
    "ko": "고른 순서대로",
    "en": "in order"
  },
  "admin.first_player_player1": {
    "ko": "플레이어1부터 (새 게임 기본값)",
    "en": "Player 1 starts (new-game default)"
  },
  "admin.first_player_deal": {
    "ko": "목적 카드 배분대로 (새 게임 기본값)",
    "en": "as the Objectives are dealt (new-game default)"
  },
  "admin.access_open": {
    "ko": "열림 (이 기기 안에서)",
    "en": "open (this machine only)"
  },
  "admin.uptime_days": {
    "ko": "{{days}}일 {{hours}}시간 {{minutes}}분",
    "en": "{{days}} d {{hours}} h {{minutes}} min"
  },
  "admin.uptime_hours": {
    "ko": "{{hours}}시간 {{minutes}}분",
    "en": "{{hours}} h {{minutes}} min"
  },
  "admin.uptime_minutes": {
    "ko": "{{minutes}}분",
    "en": "{{minutes}} min"
  },
  "admin.m_name": {
    "ko": "이름",
    "en": "Name"
  },
  "admin.m_system": {
    "ko": "운영체제",
    "en": "System"
  },
  "admin.m_cpus": {
    "ko": "CPU 수",
    "en": "CPUs"
  },
  "admin.m_load": {
    "ko": "부하 (1·5·15분)",
    "en": "Load (1, 5, 15 min)"
  },
  "admin.m_memory": {
    "ko": "메모리 (여유 / 전체)",
    "en": "Memory (free / total)"
  },
  "admin.m_process": {
    "ko": "서버 프로세스 메모리",
    "en": "Server process memory"
  },
  "admin.m_disk": {
    "ko": "디스크 (여유 / 전체)",
    "en": "Disk (free / total)"
  },
  "admin.games_none": {
    "ko": "진행 중인 게임이 없습니다.",
    "en": "No games in progress."
  },
  "admin.game_title": {
    "ko": "게임 {{id}}",
    "en": "Game {{id}}"
  },
  "admin.base_uprising": {
    "ko": "듄 임페리움: 봉기",
    "en": "Dune: Imperium - Uprising"
  },
  "admin.base_imperium": {
    "ko": "듄: 임페리움 (원판)",
    "en": "Dune: Imperium (original)"
  },
  "admin.game_waiting": {
    "ko": "시작 대기 중",
    "en": "waiting for the start"
  },
  "admin.game_round": {
    "ko": "{{round}}라운드 진행 중",
    "en": "round {{round}} in progress"
  },
  "admin.game_finished": {
    "ko": "끝난 게임",
    "en": "finished"
  },
  "admin.seat_label": {
    "ko": "플레이어{{n}}",
    "en": "Player {{n}}"
  },
  "admin.seat_open": {
    "ko": "빈 자리",
    "en": "open seat"
  },
  "admin.kind_human": {
    "ko": "사람",
    "en": "Human"
  },
  "admin.kind_app_ai": {
    "ko": "앱 AI·어려움",
    "en": "App AI (hard)"
  },
  "admin.kind_app_ai_medium": {
    "ko": "앱 AI·보통",
    "en": "App AI (medium)"
  },
  "admin.kind_app_ai_easy": {
    "ko": "앱 AI·쉬움",
    "en": "App AI (easy)"
  },
  "admin.kind_search": {
    "ko": "탐색 AI",
    "en": "Search AI"
  },
  "admin.kind_heuristic": {
    "ko": "휴리스틱 AI",
    "en": "Heuristic AI"
  },
  "admin.kind_rollout": {
    "ko": "롤아웃 탐색 AI",
    "en": "Rollout search AI"
  },
  "admin.kind_rollout_strong": {
    "ko": "강한 롤아웃 탐색 AI",
    "en": "Strong rollout search AI"
  },
  "admin.kind_random": {
    "ko": "랜덤 AI",
    "en": "Random AI"
  },
  "admin.kind_checkpoint": {
    "ko": "학습 체크포인트",
    "en": "Trained checkpoint"
  },
  "admin.online": {
    "ko": "접속 중",
    "en": "online"
  },
  "admin.offline": {
    "ko": "접속 안 함",
    "en": "offline"
  },
  "admin.turn_of": {
    "ko": "차례: {{who}}",
    "en": "Turn: {{who}}"
  },
  "admin.copy_link": {
    "ko": "방 링크 복사",
    "en": "Copy room link"
  },
  "admin.save_now": {
    "ko": "지금 저장",
    "en": "Save now"
  },
  "admin.delete_game": {
    "ko": "게임 삭제",
    "en": "Delete game"
  },
  "admin.release": {
    "ko": "자리 비우기",
    "en": "Release seat"
  },
  "admin.hand_to_ai": {
    "ko": "AI에게 맡기기",
    "en": "Let the AI play"
  },
  "admin.ai_plays": {
    "ko": "AI가 둠",
    "en": "AI plays"
  },
  "admin.confirm_delete_game": {
    "ko": "게임 {{id}}을(를) 삭제할까요? 되돌릴 수 없습니다.",
    "en": "Delete game {{id}}? This cannot be undone."
  },
  "admin.confirm_release": {
    "ko": "{{who}} 자리를 비울까요?",
    "en": "Release {{who}}'s seat?"
  },
  "admin.confirm_hand_to_ai": {
    "ko": "{{who}} 자리를 AI에게 맡길까요? 그 플레이어는 자리의 '직접 두기'로 언제든 되찾을 수 있습니다.",
    "en": "Let the AI play {{who}}'s seat? Its player can take it back with 'Play myself' at any time."
  },
  "admin.confirm_delete_save": {
    "ko": "저장본 \"{{name}}\"을(를) 삭제할까요? 되돌릴 수 없습니다.",
    "en": "Delete the save \"{{name}}\"? This cannot be undone."
  },
  "admin.done_saved": {
    "ko": "게임 {{id}}을(를) 저장했습니다.",
    "en": "Saved game {{id}}."
  },
  "admin.done_deleted_game": {
    "ko": "게임 {{id}}을(를) 삭제했습니다.",
    "en": "Deleted game {{id}}."
  },
  "admin.done_released": {
    "ko": "{{who}} 자리를 비웠습니다.",
    "en": "Released {{who}}'s seat."
  },
  "admin.done_handed": {
    "ko": "{{who}} 자리를 AI가 맡았습니다.",
    "en": "The AI now plays {{who}}'s seat."
  },
  "admin.done_loaded": {
    "ko": "저장본을 불러와 새 게임 {{id}}이(가) 되었습니다.",
    "en": "Loaded the save as the new game {{id}}."
  },
  "admin.done_deleted_save": {
    "ko": "저장본을 삭제했습니다.",
    "en": "Deleted the save."
  },
  "admin.saves_none": {
    "ko": "저장본이 없습니다.",
    "en": "No saves."
  },
  "admin.save_autosave": {
    "ko": "자동 저장",
    "en": "Autosave"
  },
  "admin.save_unnamed": {
    "ko": "이름 없음",
    "en": "Unnamed"
  },
  "admin.save_progress": {
    "ko": "{{round}}라운드 · {{phase}}",
    "en": "round {{round}} · {{phase}}"
  },
  "admin.save_finished": {
    "ko": "끝난 게임",
    "en": "finished game"
  },
  "admin.load": {
    "ko": "불러오기",
    "en": "Load"
  },
  "admin.delete_save": {
    "ko": "삭제",
    "en": "Delete"
  },
  "admin.log_none": {
    "ko": "이 서버는 로그를 모으지 않습니다",
    "en": "This server does not collect its log"
  },
  "admin.log_empty": {
    "ko": "아직 로그가 없습니다.",
    "en": "No log lines yet."
  },
  "admin.unreachable": {
    "ko": "서버에 연결할 수 없습니다.",
    "en": "Cannot reach the server."
  },
  "admin.request_failed": {
    "ko": "요청이 실패했습니다 ({{status}})",
    "en": "The request failed ({{status}})"
  }
};
