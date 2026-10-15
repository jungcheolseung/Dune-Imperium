extends Node

const BeneBoard = preload("res://bene_tleilax.gd")
var table: Control
var scouts_panel: PanelContainer
var scouts_button: Button
var scouts_index = 0
var scouts_round = -1
var scouts_items: Array = []
var scouts_manual = false
var private_line: Label


func setup(owner_table: Control) -> void:
	table = owner_table
	scouts_panel = table._panel(table.board, 10)
	scouts_panel.z_index = 12
	scouts_panel.hide()
	scouts_button = table._button(table.board_tools, table.model.native("스카웃"), toggle_scouts)
	scouts_button.custom_minimum_size.y = 28
	scouts_button.hide()


func render() -> void:
	var view = table.model.view()
	var summary = table.model.summary()
	for group in [["face_up_contract_ids", table.model.native("초암 계약")], ["revealed_contract_ids", table.model.native("공개된 계약")], ["skill_face_up", table.model.native("스킬")], ["tech_face_up", table.model.native("기술")], ["tleilaxu_row", table.model.native("틀레이락스 열")], ["scouts_auction_cards", table.model.native("경매 공개 카드")]]:
		var refs = view.get(group[0], []).filter(func(ref): return not str(ref).is_empty())
		if group[0] == "tleilaxu_row" and summary.get("immortality", false):
			refs.append("reclaimed_forces")
		if not refs.is_empty():
			_market_group(group[1], refs, group[0] in ["face_up_contract_ids", "revealed_contract_ids", "skill_face_up", "tech_face_up"])
	if summary.get("immortality", false):
		table._button(table.market_content, table.model.phrase("{bene_tleilax_board}"), open_bene)
		var board = BeneBoard.new()
		board.model = table.model
		board.api = table.api
		board.custom_minimum_size = Vector2(160, 114)
		table.market_content.add_child(board)
		board.chosen.connect(table._choose_ref)
	if not view.get("scouts_subcommittees", []).is_empty():
		_market_group(table.model.native("스카웃 소위원회"), view.scouts_subcommittees, false)
	for pile in [["intrigue_discard", table.model.native("책략 버린 더미")], ["imperium_removed", table.model.native("제외한 공용 카드")], ["contract_trash", table.model.native("폐기한 계약")], ["skill_trash", table.model.native("폐기한 스킬")], ["tech_trash", table.model.native("폐기한 기술")]]:
		var refs = view.get(pile[0], [])
		if not refs.is_empty():
			table._button(table.market_content, "%s · %d" % [pile[1], refs.size()], table._open_pile.bind(pile[1], refs))
	for count in [["imperium_deck_size", table.model.native("임페리움 덱")], ["intrigue_deck_size", table.model.native("책략 덱")], ["contract_bank_size", table.model.native("계약 보급")], ["skill_stack_size", table.model.native("스킬 더미")], ["tleilaxu_deck_size", table.model.native("틀레이락스 덱")]]:
		if view.has(count[0]) and (int(view[count[0]]) > 0 or count[0] in ["imperium_deck_size", "intrigue_deck_size"]):
			table._label(table.market_content, "%s %d" % [count[1], int(view[count[0]])], 12)
	var private = view.get("private")
	if private is Dictionary:
		var peeked: Array = []
		peeked.append_array(private.get("peeked_intrigue_ids", []))
		if not peeked.is_empty():
			table._label(table.hand, table.model.native("엿본 카드"), 13)
			for ref in peeked:
				table._card(table.hand, ref, 100, 158, false)
	_update_scouts()


func _market_group(title: String, refs: Array, landscape: bool) -> void:
	var key = table.model.section_id(str(refs[0]))[0]
	if key.is_empty():
		for section in table.Model.SECTIONS:
			if table.model.catalog.get(section, {}).has(str(refs[0])):
				key = section
				break
	if table.layout_ui.fold_header(table.market_content, title, key, table._open_pile.bind(title, refs)):
		return
	for index in range(0, refs.size(), 1 if landscape else 2):
		var row = HBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		table.market_content.add_child(row)
		for offset in range(mini(1 if landscape else 2, refs.size() - index)):
			table._card(row, str(refs[index + offset]), 160 if landscape else 76, 112 if landscape else 114)


func open_bene() -> Window:
	var parts = table.tools_ui._dialog(table.model.phrase("{bene_tleilax_board}"), Vector2i(930, 640))
	var board = BeneBoard.new()
	board.model = table.model
	board.api = table.api
	board.custom_minimum_size = Vector2(900, 615)
	parts[1].add_child(board)
	board.chosen.connect(func(ref):
		table._choose_ref(ref)
		parts[0].hide()
		parts[0].queue_free()
	)
	return parts[0]


func player_details(parent: Node, player: Dictionary) -> void:
	var model = table.model
	var seat = int(player.player)
	if int(player.get("twisted_intrigue_deck_size", 0)) > 0:
		table._label(parent, model.ui("panels.twisted_deck", {"count": int(player.twisted_intrigue_deck_size)}), 13)
	var fields = [["high_council", table.model.native("의회석")], ["swordmaster_acquired", table.model.native("검술의 달인")], ["maker_hooks", table.model.native("창조자의 갈고리")], ["family_atomics", table.model.native("가문 핵")], ["has_secret_project", table.model.native("비밀 프로젝트")]]
	var flags: PackedStringArray = []
	for pair in fields:
		if player.get(pair[0], false):
			flags.append(pair[1])
	if not flags.is_empty():
		table._label(parent, " · ".join(flags), 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if model.summary().get("bloodlines", false):
		table._label(parent, table.model.native("지휘관 · 보급 %d / 수비대 %d / 교전 %d") % [int(player.commanders_supply), int(player.commanders_garrison), int(player.commanders_conflict)], 14)
	if model.summary().get("immortality", false):
		table._label(parent, table.model.native("연구: %s · 틀레이락스 %d · 표본 %d") % [model.name_of(str(player.research_space)), int(player.tleilaxu_space), int(player.specimens)], 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for pile in [["active_contract_ids", table.model.native("진행 중 계약")], ["completed_contract_ids", table.model.native("완료한 계약")], ["skill_ids", table.model.native("스킬")], ["tech_ids", table.model.native("보유 기술")], ["imperium_set_aside", table.model.native("따로 치운 카드")], ["hand_public", table.model.native("공개적으로 알려진 손패")], ["navigation_played", table.model.native("사용한 항행 카드")]]:
		var refs = player.get(pile[0], [])
		if not refs.is_empty():
			table._button(parent, "%s · %d" % [pile[1], refs.size()], table._open_pile.bind(model.seat_name(seat) + " · " + pile[1], refs))
	if not player.get("tech_flipped", []).is_empty():
		table._label(parent, table.model.native("뒤집힌 기술: ") + _names(player.tech_flipped), 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for field in [["held_contract_icons", table.model.native("해결 대기 계약 아이콘")], ["ungained_troops", table.model.native("아직 받지 못한 병력")], ["ungained_specimens", table.model.native("아직 받지 못한 표본")], ["track_spies_owed", table.model.native("배치 대기 스파이")], ["memories", table.model.native("기억")], ["agent_in_conflict", table.model.native("교전 중 에이전트")]]:
		if int(player.get(field[0], 0)) > 0:
			table._label(parent, "%s %d" % [field[1], int(player[field[0]])], 13)
	var state = leader_words(player)
	if not state.is_empty():
		table._label(parent, state, 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if seat == model.active_seat:
		var private = model.view().get("private", {})
		for pile in [["navigation_slots", table.model.native("남은 항행 카드")], ["peeked_intrigue_ids", table.model.native("엿본 책략")]]:
			var refs = private.get(pile[0], [])
			if not refs.is_empty():
				table._button(parent, pile[1], table._open_pile.bind(pile[1], refs))
		var secret = str(private.get("secret_project_tech_id", ""))
		if not secret.is_empty():
			table._button(parent, model.name_of(secret), table._open_details.bind(secret))


func _names(refs: Array) -> String:
	var names: PackedStringArray = []
	for ref in refs:
		names.append(table.model.name_of(str(ref)))
	return " / ".join(names)


func leader_words(player: Dictionary) -> String:
	var model = table.model
	var lines: PackedStringArray = []
	if str(player.get("leader_id", "")) == "feyd_rautha_harkonnen":
		lines.append(table.model.native("훈련: ") + model.label("FEYD_TRACK_LABELS", str(player.feyd_track_space)))
	if str(player.get("leader_id", "")) == "chani":
		lines.append(table.model.native("전술: %d") % (int(player.tactics_track_space) + 1))
	if int(player.get("navigation_remaining", 0)) > 0:
		lines.append(table.model.native("남은 항행 카드 %d") % int(player.navigation_remaining))
	return "\n".join(lines)


func current_conflicts(parent: Node) -> void:
	var history = table.model.view().get("conflict_history", [])
	if not history.is_empty():
		table._button(parent, table.model.ui("board.conflict_history_button"), conflict_history)
	if table.model.view().has("disclosure"):
		table._button(parent, table.model.native("게임 종료 공개 정보"), disclosure)
	if table.model.summary().get("arrakeen_scouts", false):
		table._button(parent, table.model.native("스카웃 현황"), scouts_details)


func conflict_history() -> Window:
	var parts = table.tools_ui._dialog(table.model.ui("panels.conflict_history"))
	for entry in table.model.view().get("conflict_history", []):
		table._button(parts[1], "%d R · %s" % [int(entry.round), table.model.name_of(str(entry.conflict_id))], table._open_details.bind(str(entry.conflict_id)))
		table._label(parts[1], table._entry_words(table.model.entry(str(entry.conflict_id)), str(entry.conflict_id)), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return parts[0]


func disclosure() -> Window:
	var data = table.model.view().get("disclosure", {})
	var parts = table.tools_ui._dialog(table.model.native("게임 종료 공개 정보 / Disclosed information"))
	for zone in ["players", "player_zones"]:
		for player in data.get(zone, []):
			var seat = int(player.get("player", player.get("seat", 0)))
			table._label(parts[1], table.model.seat_name(seat), 19)
			for key in player:
				if player[key] is Array and not player[key].is_empty() and player[key][0] is String:
					table._button(parts[1], table.model.label("PAYLOAD_KEY_LABELS", str(key)) + " · " + str(player[key].size()), table._open_pile.bind(table.model.label("PAYLOAD_KEY_LABELS", str(key)), player[key], key == "deck"))
	for key in ["imperium_deck", "intrigue_deck", "contract_bank", "conflict_deck", "scouts_board_cards"]:
		var refs = data.get(key, [])
		if not refs.is_empty():
			table._button(parts[1], table.model.label("PAYLOAD_KEY_LABELS", key) + " · " + str(refs.size()), table._open_pile.bind(table.model.label("PAYLOAD_KEY_LABELS", key), refs, true))
	for row in data.get("scouts_secret_picks", []):
		table._label(parts[1], table.model.native("%d R · %s · %s · 선택 %d") % [int(row[0]), table.model.name_of(str(row[1])), table.model.seat_name(int(row[2])), int(row[3]) + 1], 14)
	for row in data.get("scouts_bids", []):
		table._label(parts[1], table.model.native("입찰 · %s · %d") % [table.model.seat_name(int(row[0])), int(row[1])], 14)
	return parts[0]


func toggle_scouts() -> void:
	scouts_manual = not scouts_panel.visible
	table.tools_ui.prefs.scouts_folded = not scouts_manual
	table.tools_ui.save_preferences()
	_update_scouts()


static func scouts_visible(has_items: bool, resolving: bool, folded: bool, manual: bool) -> bool:
	return has_items and not folded and (resolving or manual)


func _update_scouts() -> void:
	var view = table.model.view()
	scouts_button.visible = table.model.summary().get("arrakeen_scouts", false)
	scouts_items.clear()
	for entry in view.get("scouts_revealed", []):
		if int(entry[0]) == int(view.get("round_number", -1)):
			scouts_items.append(str(entry[1]))
	var resolving = str(view.get("scouts_item", ""))
	var payload = table.model.snapshot.get("actions")
	if resolving == "secrets" and payload is Dictionary and payload.get("scouts_lines") is Dictionary and payload.scouts_lines.get("item_id") != null:
		resolving = str(payload.scouts_lines.item_id)
	if resolving == "secrets":
		resolving = ""
	if not resolving.is_empty() and resolving not in scouts_items:
		scouts_items.append(resolving)
	if scouts_round != int(view.get("round_number", -1)):
		scouts_round = int(view.get("round_number", -1))
		scouts_manual = false
		scouts_index = maxi(0, scouts_items.find(resolving))
	var is_resolving = not str(view.get("scouts_item", "")).is_empty() and not table.model.summary().get("finished", false)
	if not scouts_visible(not scouts_items.is_empty(), is_resolving, table.tools_ui.prefs.get("scouts_folded", false), scouts_manual):
		scouts_panel.hide()
		return
	table._clear(scouts_panel)
	var body = VBoxContainer.new()
	scouts_panel.add_child(body)
	var header = HBoxContainer.new()
	body.add_child(header)
	if scouts_items.size() > 1:
		table._button(header, "◀", func(): scouts_index = posmod(scouts_index - 1, scouts_items.size()); _update_scouts())
		table._button(header, "▶", func(): scouts_index = (scouts_index + 1) % scouts_items.size(); _update_scouts())
	scouts_index = clampi(scouts_index, 0, scouts_items.size() - 1)
	var ref = str(scouts_items[scouts_index])
	var title = table._label(header, table.model.name_of(ref), 18)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	table._button(header, "×", toggle_scouts).custom_minimum_size.y = 28
	var description = table._scroll(body)
	var entry = table.model.entry(ref)
	if entry.get("currency") != null:
		table._label(description, table.model.ui("panels.scouts_currency") + " " + table.model.phrase("{" + str(entry.currency) + "}"), 14)
	for line in table.model.localized(entry, "lines") if table.model.localized(entry, "lines") is Array else []:
		table._label(description, table.model.phrase(line), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if not resolving.is_empty() and ref == resolving:
		table._label(description, table.model.prompt(), 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	scouts_panel.size = Vector2(clampf(table.board.size.x * 0.9, 300, 570), clampf(table.board.size.y * 0.7, 200, 370))
	scouts_panel.position = Vector2((table.board.size.x - scouts_panel.size.x) / 2, 8)
	scouts_panel.show()


func scouts_details() -> Window:
	var view = table.model.view()
	var parts = table.tools_ui._dialog(table.model.native("스카웃 현황 / Arrakeen Scouts"))
	for entry in view.get("scouts_revealed", []):
		table._button(parts[1], "%d R · %s" % [int(entry[0]), table.model.name_of(str(entry[1]))], table._open_details.bind(str(entry[1])))
	for row in view.get("scouts_subcommittee_members", []):
		table._label(parts[1], "%s · %s" % [table.model.name_of(str(row[0])), table.model.seat_name(int(row[1]))], 15)
	for row in view.get("scouts_goods", []):
		table._label(parts[1], "%s · %s · %s %d · %s" % [table.model.name_of(str(row[0])), location_name(str(row[1])), table.model.phrase("{" + str(row[2]) + "}"), int(row[3]), table.model.seat_name(int(row[4])) if int(row[4]) >= 0 else table.model.ui("panels.scouts_anyone")], 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for row in view.get("scouts_parked", []):
		table._label(parts[1], table.model.native("%s · %s · %s · 병력 %d") % [table.model.name_of(str(row[0])), table.model.seat_name(int(row[1])), location_name(str(row[2])), int(row[3])], 14)
	for row in view.get("scouts_board_card_counts", []):
		table._label(parts[1], table.model.native("%s · %s · 비공개 카드 %d") % [table.model.name_of(str(row[0])), location_name(str(row[1])), int(row[2])], 14)
	for row in view.get("scouts_secret_pending", []):
		table._label(parts[1], table.model.native("%d R · %s · %s · 아직 비공개") % [int(row[0]), table.model.name_of(str(row[1])), table.model.seat_name(int(row[2]))], 14)
	var own = view.get("private", {})
	if not view.get("scouts_bids_confirmed", []).is_empty():
		var names: PackedStringArray = []
		for seat in view.scouts_bids_confirmed:
			names.append(table.model.seat_name(int(seat)))
		table._label(parts[1], table.model.ui("panels.scouts_bids", {"seats": ", ".join(names)}), 14)
	for row in own.get("scouts_secret_picks", []):
		var lines = table.model.localized(table.model.entry(str(row[1])), "lines")
		var picked = lines[int(row[2])] if lines is Array and lines.size() > int(row[2]) else str(int(row[2]) + 1)
		table._label(parts[1], table.model.native("%d R · %s · 내 선택: %s") % [int(row[0]), table.model.name_of(str(row[1])), table.model.phrase(picked)], 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if int(own.get("scouts_bid", -1)) >= 0:
		table._label(parts[1], table.model.native("내 봉인 입찰: %d") % int(own.scouts_bid), 14)
	for row in view.get("scouts_calls", []):
		table._label(parts[1], table.model.native("공개 입찰: %s · %d") % [table.model.seat_name(int(row[0])), int(row[1])], 14)
	return parts[0]


func decision_header(parent: Node) -> void:
	var top = table.model.top_choice_card()
	if not top.is_empty():
		table._label(parent, table.model.ui("panels.deck_top_badge"), 14)
		var card = table._card(parent, top, 146, 210, false)
		card.set_meta("deck_top_choice", true)
	var cursor = str(table.model.view().get("scouts_item", ""))
	if cursor.is_empty():
		return
	var payload = table.model.snapshot.get("actions")
	var id = cursor
	if payload is Dictionary and payload.get("scouts_lines") is Dictionary and payload.scouts_lines.get("item_id") != null:
		id = str(payload.scouts_lines.item_id)
	var item = table.model.entry(id)
	var title = table.model.ui("render.scouts_decision_secrets") if item.is_empty() else table.model.ui("render.scouts_decision_secret_item", {"name": table.model.name_of(id)}) if cursor == "secrets" else table.model.ui("render.scouts_decision_item", {"kind": table.model.ui("panels.scouts_kind_" + str(item.get("kind", "event"))), "name": table.model.name_of(id)})
	table._label(parent, title, 17).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if item.get("currency") != null:
		table._label(parent, table.model.ui("panels.scouts_currency") + " " + table.model.phrase("{" + str(item.currency) + "}"), 14)
	var rows_are_lines = payload is Dictionary and payload.get("scouts_lines") is Dictionary and payload.scouts_lines.get("frame") == "scouts_choice"
	if not rows_are_lines:
		for line in table.model.localized(item, "lines") if table.model.localized(item, "lines") is Array else []:
			table._label(parent, table.model.phrase(line), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func location_name(id: String) -> String:
	if id == "helix":
		return table.model.phrase("{genetic_marker}")
	if id == "tleilaxu_track":
		return table.model.phrase("{tleilaxu_track}")
	if id.begins_with("contract:"):
		return table.model.name_of(id.trim_prefix("contract:"))
	if id.begins_with("post:"):
		id = id.trim_prefix("post:")
	if id in table.model.catalog.get("post_spaces", {}):
		return table.model.native("관측소 · ") + _names(table.model.catalog.post_spaces[id])
	return table.model.name_of(id)


func leader_detail(parent: Node, ref: String) -> void:
	var player = table.model.leader_player(ref)
	if player.is_empty():
		return
	var words = leader_words(player)
	if not words.is_empty():
		table._label(parent, words, 15).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var played = player.get("navigation_played", [])
	var remaining = int(player.get("navigation_remaining", 0))
	if not played.is_empty() or remaining > 0:
		table._label(parent, table.model.native("항행 카드"), 14)
		var row = HFlowContainer.new()
		parent.add_child(row)
		for card in played:
			table._card(row, str(card), 128, 212, false)
		if int(player.player) == table.model.active_seat:
			for card in table.model.view().get("private", {}).get("navigation_slots", []):
				table._card(row, str(card), 128, 212, false)
		elif remaining > 0:
			table._label(parent, table.model.native("비공개 %d장") % remaining, 13)
	if player.get("has_secret_project", false):
		var secret = str(table.model.view().get("private", {}).get("secret_project_tech_id", "")) if int(player.player) == table.model.active_seat else ""
		if not secret.is_empty():
			var row = HBoxContainer.new()
			parent.add_child(row)
			table._card(row, secret, 210, 180, false)
		else:
			table._label(parent, table.model.native("비밀 프로젝트 · 비공개"), 13)
	if str(player.get("leader_id", "")) == "shaddam_corrino_iv":
		var contracts = table.model.view().get("sardaukar_contract_ids", [])
		if not contracts.is_empty():
			var row = HFlowContainer.new()
			parent.add_child(row)
			for card in contracts:
				table._card(row, str(card), 210, 180, false)
