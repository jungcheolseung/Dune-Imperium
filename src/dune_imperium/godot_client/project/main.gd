extends Control

const Api = preload("res://api.gd")
const Model = preload("res://model.gd")
const Board = preload("res://board.gd")

var api = Api.new()
var model = Model.new()
var game_id = ""
var busy = false
var refreshing = false
var generation = 0
var tab = "choices"
var inspect_ref = ""
var images: Array[TextureRect] = []
var smoke = false
var smoke_done = false
var capture_dir = ""
var closing = false
var poll_timer: Timer

var status: Label
var round_label: Label
var seats: HBoxContainer
var hand: HBoxContainer
var content: VBoxContainer
var inspector_title: Label
var inspector_words: Label
var inspector_image: TextureRect
var finish_button: Button
var undo_button: Button
var save_button: Button
var new_button: Button
var selection: Label
var board: Control
var own_line: Label


func _ready() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--server="):
			api.base_url = argument.trim_prefix("--server=").trim_suffix("/")
		elif argument.begins_with("--labels="):
			var file = FileAccess.open(argument.trim_prefix("--labels="), FileAccess.READ)
			if file != null:
				var parsed = JSON.parse_string(file.get_as_text())
				if parsed is Dictionary:
					model.words = parsed
		elif argument == "--smoke":
			smoke = true
		elif argument.begins_with("--capture="):
			capture_dir = argument.trim_prefix("--capture=")
	_build_theme()
	_build_table()
	add_child(api)
	api.texture_ready.connect(_texture_ready)
	var timer = Timer.new()
	poll_timer = timer
	timer.wait_time = 0.8
	timer.timeout.connect(_poll)
	add_child(timer)
	timer.start()
	get_window().min_size = Vector2i(1100, 740)
	get_tree().auto_accept_quit = false
	var catalog = await api.call_json(HTTPClient.METHOD_GET, "/catalog")
	if catalog.ok:
		model.catalog = catalog.data
		new_button.disabled = false
		status.text = "새 게임을 눌러 출발하세요"
		if model.catalog.get("board_image") != null:
			board.board_texture = api.texture(str(model.catalog.board_image))
		board.queue_redraw()
	else:
		status.text = "서버에 연결하지 못했습니다. 다시 실행해 주세요."
	if smoke:
		var watchdog = Timer.new()
		watchdog.wait_time = 90
		watchdog.one_shot = true
		watchdog.timeout.connect(func(): _smoke_fail("timeout"))
		add_child(watchdog)
		watchdog.start()
		_run_smoke()
	elif not capture_dir.is_empty():
		_run_capture()


func _build_theme() -> void:
	theme = Theme.new()
	theme.default_font = load("res://fonts/NanumGothic-Regular.ttf")
	theme.default_font_size = 16
	theme.set_color("font_color", "Label", Color("efe9dd"))
	theme.set_color("font_color", "Button", Color("efe9dd"))
	theme.set_color("font_hover_color", "Button", Color.WHITE)
	theme.set_color("font_disabled_color", "Button", Color("747d85"))
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var style = _style(Color("222d36"), Color("40515e"))
		if state == "hover":
			style.bg_color = Color("34434f")
			style.border_color = Color("d9b67e")
		elif state == "pressed":
			style.bg_color = Color("4b4031")
			style.border_color = Color("e5bf7d")
		elif state == "disabled":
			style.bg_color = Color("1b232a")
		theme.set_stylebox(state, "Button", style)
	theme.set_constant("separation", "VBoxContainer", 10)
	theme.set_constant("separation", "HBoxContainer", 10)


func _style(background: Color, border: Color = Color("35414b")) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(10)
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	return style


func _panel(parent: Node, padding = 12) -> PanelContainer:
	var panel = PanelContainer.new()
	var style = _style(Color("141e26"))
	style.content_margin_left = padding
	style.content_margin_right = padding
	style.content_margin_top = padding
	style.content_margin_bottom = padding
	panel.add_theme_stylebox_override("panel", style)
	parent.add_child(panel)
	return panel


func _label(parent: Node, text: String, font_size = 16) -> Label:
	var label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	parent.add_child(label)
	return label


func _button(parent: Node, text: String, callback: Callable) -> Button:
	var button = Button.new()
	button.text = text
	button.custom_minimum_size.y = 42
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _scroll(parent: Node) -> VBoxContainer:
	var scroll = ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var body = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(body)
	return body


func _build_table() -> void:
	var margin = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for key in ["margin_left", "margin_right", "margin_top", "margin_bottom"]:
		margin.add_theme_constant_override(key, 18)
	add_child(margin)
	var root = VBoxContainer.new()
	root.add_theme_constant_override("separation", 14)
	margin.add_child(root)
	var header = HBoxContainer.new()
	root.add_child(header)
	var branding = VBoxContainer.new()
	header.add_child(branding)
	_label(branding, "DUNE  /  IMPERIUM", 28).add_theme_color_override("font_color", Color("dfbd84"))
	_label(branding, "봉기 · 아라키스의 주인이 되세요", 13)
	round_label = _label(header, "", 20)
	round_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	round_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	new_button = _button(header, "새 게임", _new_game)
	new_button.disabled = true
	save_button = _button(header, "저장", _save)
	save_button.disabled = true
	undo_button = _button(header, "되돌리기", _undo)
	undo_button.disabled = true
	seats = HBoxContainer.new()
	root.add_child(seats)
	var middle = HBoxContainer.new()
	middle.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(middle)
	var board_panel = _panel(middle, 4)
	board_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var board_stack = VBoxContainer.new()
	board_panel.add_child(board_stack)
	var board_tools = HBoxContainer.new()
	board_stack.add_child(board_tools)
	_label(board_tools, "보드 위에서 휠: 확대 · 가운데 버튼 드래그: 이동", 12).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_button(board_tools, "전체 보기", _reset_board)
	board = Board.new()
	board.model = model
	board.size_flags_vertical = Control.SIZE_EXPAND_FILL
	board.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board.custom_minimum_size = Vector2(450, 340)
	board.chosen.connect(_choose_ref)
	board.inspected.connect(_inspect)
	board_stack.add_child(board)
	selection = _label(board_stack, "카드와 칸을 선택해 에이전트를 보내세요", 15)
	selection.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	selection.custom_minimum_size.y = 28
	var side = _panel(middle)
	side.custom_minimum_size.x = 360
	var stack = VBoxContainer.new()
	side.add_child(stack)
	var tabs = HBoxContainer.new()
	stack.add_child(tabs)
	for item in [["choices", "선택"], ["market", "시장"], ["log", "기록"]]:
		var button = _button(tabs, item[1], _set_tab.bind(item[0]))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var preview = HBoxContainer.new()
	preview.custom_minimum_size.y = 150
	stack.add_child(preview)
	inspector_image = TextureRect.new()
	inspector_image.custom_minimum_size = Vector2(104, 146)
	inspector_image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	inspector_image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	preview.add_child(inspector_image)
	var description = _scroll(preview)
	inspector_title = _label(description, "테이블을 살펴보세요", 18)
	inspector_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector_words = _label(description, "카드나 칸 위에 마우스를 올리면 여기에서 자세히 볼 수 있습니다.", 14)
	inspector_words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content = _scroll(stack)
	finish_button = _button(stack, "턴 종료 ▶", _finish)
	finish_button.custom_minimum_size.y = 54
	finish_button.add_theme_font_size_override("font_size", 20)
	finish_button.add_theme_stylebox_override("normal", _style(Color("514330"), Color("d7b178")))
	finish_button.disabled = true
	var hand_panel = _panel(root)
	var hand_stack = VBoxContainer.new()
	hand_panel.add_child(hand_stack)
	own_line = _label(hand_stack, "내 손패", 17)
	var hand_scroll = ScrollContainer.new()
	hand_scroll.custom_minimum_size.y = 180
	hand_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	hand_stack.add_child(hand_scroll)
	hand = HBoxContainer.new()
	hand.add_theme_constant_override("separation", 12)
	hand_scroll.add_child(hand)
	status = _label(root, "테이블을 준비하고 있습니다…", 13)
	status.add_theme_color_override("font_color", Color("9caebc"))


func _clear(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()


func _new_game() -> void:
	await _create_game(null)


func _create_game(seed: Variant) -> bool:
	if busy or model.catalog.is_empty():
		return false
	busy = true
	generation += 1
	status.text = "아라키스로 떠나는 중…"
	var result = await api.call_json(HTTPClient.METHOD_POST, "/games", {"seats": ["human", "app_ai", "app_ai", "app_ai"], "game_seed": seed, "ai_pace": "fast"})
	busy = false
	if not _accept(result):
		return false
	game_id = result.data.game_id
	model.snapshot = {}
	inspect_ref = ""
	tab = "choices"
	await _sync()
	return true


func _accept(reply: Dictionary) -> bool:
	if reply.ok:
		return true
	var detail = reply.data.get("detail", "연결이 끊겼습니다. 다시 시도해 주세요.")
	status.text = "처리하지 못했습니다: " + str(detail)
	return false


func _poll() -> void:
	if not closing and not busy and not refreshing and not game_id.is_empty():
		_sync()


func _sync() -> bool:
	while refreshing:
		await get_tree().process_frame
	if game_id.is_empty():
		return false
	refreshing = true
	var requested_game = game_id
	var requested_generation = generation
	var reply = await api.call_json(HTTPClient.METHOD_GET, "/games/" + game_id + "/snapshot?seat=0")
	refreshing = false
	if requested_game != game_id or requested_generation != generation:
		return false
	if not _accept(reply):
		return false
	var changed = model.adopt(reply.data)
	if changed:
		_render()
	return true


func _render() -> void:
	var summary = model.summary()
	var view = model.view()
	new_button.disabled = busy
	save_button.disabled = busy or game_id.is_empty()
	undo_button.disabled = busy
	if not busy:
		undo_button.disabled = true
		for item in summary.get("undo", []):
			if int(item.seat) == 0 and int(item.steps) > 0:
				undo_button.disabled = false
	round_label.text = "%d 라운드  /  %s" % [int(summary.get("round_number", 0)), model.label("PHASE_LABELS", summary.get("phase", ""))]
	_clear(seats)
	for player in view.get("players", []):
		var seat = int(player.player)
		var panel = _panel(seats, 10)
		panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var accent = Model.SEAT_COLORS[seat]
		panel.add_theme_stylebox_override("panel", _style(Color("18232c"), accent))
		var stack = VBoxContainer.new()
		panel.add_child(stack)
		var who = "나" if seat == 0 else "앱 AI %d" % seat
		var leader = _label(stack, "%s · %s" % [who, model.name_of(str(player.leader_id))], 15)
		leader.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		var resources = player.get("resources", {})
		_label(stack, "%d점    솔라리 %d  ·  스파이스 %d  ·  물 %d" % [int(player.victory_points), int(resources.get("solari", 0)), int(resources.get("spice", 0)), int(resources.get("water", 0))], 14)
		_label(stack, "에이전트 %d  ·  수비대 %d  ·  전투력 %d  ·  책략 %d" % [int(player.agents_available), int(player.troops_garrison), int(player.combat_strength), int(player.intrigue_card_count)], 13)
		panel.mouse_entered.connect(_inspect.bind(str(player.leader_id)))
	_clear(hand)
	images = images.filter(func(image): return is_instance_valid(image))
	var private = view.get("private", {})
	var hand_cards = private.get("hand", [])
	var intrigues = private.get("intrigue_cards", [])
	own_line.text = "내 손패  %d장    /    책략 %d장" % [hand_cards.size(), intrigues.size()]
	for ref in hand_cards:
		_card(hand, ref, 124, 164)
	if not intrigues.is_empty():
		var separator = VSeparator.new()
		hand.add_child(separator)
		for ref in intrigues:
			_card(hand, ref, 114, 164)
	board.refresh()
	var conflicts = view.get("current_conflict_ids", [])
	if not conflicts.is_empty():
		var entry = model.entry(conflicts[0])
		board.set_meta("conflict_path", _image_path(entry))
		board.conflict_texture = api.texture(_image_path(entry))
	_render_choices()
	_update_inspector()
	if summary.get("finished", false):
		status.text = "게임이 끝났습니다. 승점과 최종 순위는 오른쪽에서 확인하세요."
	elif summary.get("thinking") != null:
		status.text = "앱 AI %d의 차례입니다…" % int(summary.thinking)
	else:
		status.text = "카드를 고르고 보드의 칸을 선택하세요. 배치 후 남은 효과를 해결하면 턴을 끝낼 수 있습니다."


func _image_path(entry: Dictionary) -> String:
	var value = model.localized(entry, "image")
	return str(value) if value != null else ""


func _card(parent: Node, ref: String, width: int, height: int) -> void:
	var button = Button.new()
	button.custom_minimum_size = Vector2(width, height)
	button.tooltip_text = model.name_of(ref)
	button.set_meta("instance_ref", ref)
	button.pressed.connect(_choose_ref.bind(ref))
	button.mouse_entered.connect(_inspect.bind(ref))
	button.gui_input.connect(func(event):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
			_open_details(ref)
	)
	var color = Color("d8b77b") if model.selected_card == ref else Color("3a4b59")
	if not model.ref_actions(ref).is_empty():
		color = Color("b89965")
	button.add_theme_stylebox_override("normal", _style(Color("18222c"), color))
	parent.add_child(button)
	var picture = TextureRect.new()
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	picture.position = Vector2(4, 4)
	picture.size = Vector2(width - 8, height - 36)
	var path = _image_path(model.entry(ref))
	picture.set_meta("image_path", path)
	picture.texture = api.texture(path)
	button.add_child(picture)
	images.append(picture)
	var caption = _label(button, model.name_of(ref), 13)
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caption.position = Vector2(7, height - 29)
	caption.size = Vector2(width - 14, 25)
	caption.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if path.is_empty():
		var fallback = _label(button, _entry_words(model.entry(ref)), 13)
		fallback.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fallback.position = Vector2(10, 16)
		fallback.size = Vector2(width - 20, height - 55)
		fallback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		fallback.clip_text = true


func _texture_ready(path: String, texture: Texture2D) -> void:
	for picture in images:
		if is_instance_valid(picture) and picture.get_meta("image_path", "") == path:
			picture.texture = texture
	if model.catalog.get("board_image") == path:
		board.board_texture = texture
		board.queue_redraw()
	if board.get_meta("conflict_path", "") == path:
		board.conflict_texture = texture
		board.queue_redraw()
	if inspector_image.get_meta("image_path", "") == path:
		inspector_image.texture = texture


func _choose_ref(ref: String) -> void:
	if busy:
		return
	_inspect(ref)
	var placements = model.placements()
	if not placements.is_empty():
		if not model.placements(ref).is_empty():
			model.selected_card = "" if model.selected_card == ref else ref
			if model.placements(model.selected_card, model.selected_space).is_empty():
				model.selected_space = ""
		elif not model.placements("", ref).is_empty():
			if not model.selected_card.is_empty() and model.placements(model.selected_card, ref).is_empty():
				status.text = "선택한 카드로는 이 칸에 갈 수 없습니다. 다른 카드나 칸을 선택하세요."
				return
			model.selected_space = "" if model.selected_space == ref else ref
		else:
			return
		tab = "choices"
		_render()
	else:
		var candidates = model.ref_actions(ref)
		if candidates.size() == 1:
			_choose_action(candidates[0], model.signature())
		elif candidates.size() > 1:
			tab = "choices"
			_render_choices(candidates)


func _set_tab(value: String) -> void:
	tab = value
	_render_choices()


func _reset_board() -> void:
	board.reset_view()


func _action_button(action: Dictionary) -> void:
	var button = _button(content, model.describe(action), _choose_action.bind(action, model.signature()))
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button.disabled = busy
	if int(model.held_action().get("index", -1)) == int(action.index):
		button.add_theme_stylebox_override("normal", _style(Color("53442f"), Color("e1bd7c")))


func _render_choices(filtered: Array = []) -> void:
	_clear(content)
	finish_button.disabled = true
	finish_button.text = "턴 종료 ▶"
	selection.text = "카드와 칸을 선택해 에이전트를 보내세요"
	if not model.selected_card.is_empty():
		selection.text = model.name_of(model.selected_card) + "  →  " + (model.name_of(model.selected_space) if not model.selected_space.is_empty() else "칸을 선택하세요")
	var held = model.held_action()
	if not held.is_empty():
		finish_button.text = "선택 확정 ▶"
		finish_button.disabled = busy
	elif model.summary().get("confirmation") == 0:
		finish_button.disabled = busy
	else:
		for action in model.actions():
			if action.action_id in Model.END_ACTIONS:
				finish_button.disabled = busy
				break
	if tab == "market":
		_render_market()
		return
	if tab == "log":
		_render_log()
		return
	if model.summary().get("finished", false):
		_label(content, "최종 순위", 22)
		for standing in model.summary().get("standings", []):
			var seat = int(standing.get("player", 0))
			var who = "나" if seat == 0 else "앱 AI %d" % seat
			_label(content, "%d위 · %s · %d점" % [int(standing.get("rank", 0)), who, int(standing.get("victory_points", 0))], 18)
		return
	var prompt = _label(content, model.prompt() if not model.prompt().is_empty() else "다른 플레이어의 차례입니다", 18)
	prompt.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if model.summary().get("confirmation") == 0:
		_label(content, "선택을 바꾸려면 되돌리기를, 마치려면 턴 종료를 누르세요.", 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if not filtered.is_empty():
		for action in filtered:
			_action_button(action)
		return
	if not model.placements().is_empty():
		if not model.selected_card.is_empty() and not model.selected_space.is_empty():
			for action in model.placements(model.selected_card, model.selected_space):
				_action_button(action)
		elif not model.selected_card.is_empty():
			var spaces: Dictionary = {}
			for action in model.placements(model.selected_card):
				spaces[action.arguments.space_id] = true
			for space in spaces:
				var button = _button(content, model.name_of(space), _choose_ref.bind(space))
				button.mouse_entered.connect(_inspect.bind(space))
		elif not model.selected_space.is_empty():
			var cards: Dictionary = {}
			for action in model.placements("", model.selected_space):
				cards[action.arguments.card_id] = true
			for card in cards:
				_button(content, model.name_of(card), _choose_ref.bind(card))
		else:
			_label(content, "손패의 카드를 고르면 보드에서 갈 수 있는 칸이 빛납니다.", 15).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for action in model.actions():
		if action.action_id != "agent_turn" and action.action_id not in Model.END_ACTIONS:
			_action_button(action)


func _render_market() -> void:
	_label(content, "임페리움 열", 20)
	var row = model.view().get("imperium_row", [])
	for index in range(0, row.size(), 2):
		var pair = HBoxContainer.new()
		content.add_child(pair)
		_card(pair, row[index], 146, 192)
		if index + 1 < row.size():
			_card(pair, row[index + 1], 146, 192)
	_label(content, "예비 더미", 18)
	for stack in model.view().get("reserve_stacks", []):
		var entry = model.entry(str(stack[0]))
		var label = "%s · %d장" % [model.name_of(str(stack[0])), int(stack[1])]
		var button = _button(content, label, _inspect.bind(str(stack[0])))
		button.mouse_entered.connect(_inspect.bind(str(stack[0])))
		for action in model.actions():
			if action.action_id.begins_with("acquire_reserve") and str(stack[0]) in action.arguments.values():
				_action_button(action)


func _render_log() -> void:
	_label(content, "이번 판의 기록", 20)
	var entries = model.snapshot.get("log", {}).get("entries", [])
	for index in range(entries.size() - 1, maxi(-1, entries.size() - 31), -1):
		var entry = entries[index]
		if entry.get("undone", false):
			continue
		var text = ""
		if entry.get("type") == "action":
			text = "%s · %s" % ["나" if int(entry.get("actor", -1)) == 0 else "앱 AI %d" % int(entry.get("actor", -1)), model.describe(entry)]
		else:
			for event in entry.get("events", []):
				text += model.label("EVENT_LABELS", str(event.get("kind", ""))) + "\n"
		if not text.is_empty():
			_label(content, text, 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _inspect(ref: String) -> void:
	inspect_ref = ref
	_update_inspector()


func _entry_words(entry: Dictionary) -> String:
	var parts: PackedStringArray = []
	var cost = entry.get("cost")
	if cost != null and not cost is Dictionary:
		parts.append("설득 비용 %d" % int(cost))
	var icons = entry.get("agent_icons", [])
	if not icons.is_empty():
		var names: PackedStringArray = []
		for icon in icons:
			names.append(model.label("AGENT_ICON_GROUPS", icon))
		parts.append("에이전트: " + " / ".join(names))
	if int(entry.get("persuasion", 0)) or int(entry.get("swords", 0)):
		parts.append("공개: 설득 비용 %d · 검 %d" % [int(entry.get("persuasion", 0)), int(entry.get("swords", 0))])
	var text = model.localized(entry, "text")
	if text is Array:
		for line in text:
			parts.append(model.phrase(line))
	for option in entry.get("options", []):
		var cost_words = model.cost_text(option.get("cost", {}))
		parts.append((cost_words + " → " if not cost_words.is_empty() else "") + model.phrase(model.localized(option, "effect")))
	for key in ["ability_text", "signet_text"]:
		var value = model.localized(entry, key)
		if value != null:
			parts.append(model.phrase(value))
	var notes = model.localized(entry, "notes")
	if notes is Array:
		for line in notes:
			parts.append(model.phrase(line))
	return "\n\n".join(parts)


func _update_inspector() -> void:
	if inspect_ref.is_empty():
		return
	var entry = model.entry(inspect_ref)
	inspector_title.text = model.name_of(inspect_ref)
	inspector_words.text = _entry_words(entry)
	var path = _image_path(entry)
	inspector_image.set_meta("image_path", path)
	inspector_image.texture = api.texture(path)


func _open_details(ref: String) -> void:
	var dialog = AcceptDialog.new()
	dialog.title = model.name_of(ref)
	dialog.dialog_text = ""
	dialog.ok_button_text = "닫기"
	dialog.theme = theme
	var row = HBoxContainer.new()
	row.custom_minimum_size = Vector2(620, 460)
	dialog.add_child(row)
	var image = TextureRect.new()
	image.custom_minimum_size = Vector2(310, 440)
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var path = _image_path(model.entry(ref))
	image.texture = api.texture(path)
	image.set_meta("image_path", path)
	images.append(image)
	row.add_child(image)
	var body = _scroll(row)
	_label(body, model.name_of(ref), 22).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_label(body, _entry_words(model.entry(ref)), 18).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()


func _choose_action(action: Dictionary, expected: String) -> void:
	if busy or expected != model.signature():
		return
	if action.get("sent_by_turn_end", false):
		if int(model.held_action().get("index", -1)) == int(action.index):
			model.held.clear()
		else:
			model.hold(action)
		_render_choices()
		return
	await _send_action(action)


func _send_action(action: Dictionary) -> bool:
	if busy:
		return false
	busy = true
	generation += 1
	_render_choices()
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/actions", model.request_body(action))
	busy = false
	var accepted = _accept(reply)
	await _sync()
	return accepted


func _finish() -> void:
	if busy:
		return
	var held = model.held_action()
	if not held.is_empty():
		await _send_action(held)
	elif model.summary().get("confirmation") == 0:
		await _mutate("confirm", {})
	else:
		for action in model.actions():
			if action.action_id in Model.END_ACTIONS:
				await _send_action(action)
				return


func _mutate(path: String, extra: Dictionary) -> bool:
	if busy:
		return false
	busy = true
	generation += 1
	var data = {"seat": 0, "revision": int(model.summary().revision), "undo_count": int(model.summary().undo_count)}
	data.merge(extra)
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/" + path, data)
	busy = false
	var accepted = _accept(reply)
	await _sync()
	return accepted


func _undo() -> void:
	await _mutate("undo", {"steps": 1})


func _save() -> void:
	if game_id.is_empty() or busy:
		return
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/save", {"name": "Godot 시제품"})
	if _accept(reply):
		status.text = "현재 판을 저장했습니다."


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.physical_keycode == KEY_ESCAPE:
		model.selected_card = ""
		model.selected_space = ""
		model.held.clear()
		_render()


func _smoke_fail(message: String) -> void:
	if not smoke_done:
		smoke_done = true
		push_error("GODOT_SMOKE_FAILED: " + message)
		get_tree().quit(1)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_quit_cleanly()


func _quit_cleanly() -> void:
	closing = true
	if poll_timer != null:
		poll_timer.stop()
	while busy or refreshing or api.image_workers > 0:
		await get_tree().process_frame
	await get_tree().process_frame
	get_tree().quit(0)


func _run_smoke() -> void:
	if not await _create_game(11):
		_smoke_fail("create game")
		return
	var first = model.placements()[0]
	_choose_ref(first.arguments.card_id)
	_choose_ref(first.arguments.space_id)
	if model.placements(model.selected_card, model.selected_space).is_empty():
		_smoke_fail("card and board selection")
		return
	if not await _send_action(first):
		_smoke_fail("place agent")
		return
	if int(model.summary().revision) <= 0:
		_smoke_fail("server state did not advance")
		return
	if not await _mutate("undo", {"steps": 1}):
		_smoke_fail("undo")
		return
	if int(model.summary().undo_count) != 1 or int(model.summary().revision) != 0:
		_smoke_fail("undo generation")
		return
	for step in range(30):
		var has_end = model.summary().get("confirmation") == 0
		for action in model.actions():
			if action.action_id in Model.END_ACTIONS:
				has_end = true
		if has_end:
			await _finish()
			break
		if model.actions().is_empty():
			_smoke_fail("no choices")
			return
		if not await _send_action(model.actions()[0]):
			_smoke_fail("effect choice")
			return
	for attempt in range(50):
		await get_tree().create_timer(0.1).timeout
		await _sync()
		var decision = model.summary().get("decision")
		if decision is Dictionary and int(decision.get("owner", -1)) == 0 and model.summary().get("thinking") == null:
			print("GODOT_SMOKE_OK ", JSON.stringify({"revision": model.summary().revision, "undo_count": model.summary().undo_count, "legal_actions": model.actions().size()}))
			smoke_done = true
			await _quit_cleanly()
			return
	_smoke_fail("AI did not hand back the turn")


func _run_capture() -> void:
	if not await _create_game(11):
		_smoke_fail("capture create")
		return
	for attempt in range(100):
		if api.image_workers == 0:
			break
		await get_tree().create_timer(0.1).timeout
	await _capture("table")
	var first = model.placements()[0]
	var card: Button
	for child in hand.get_children():
		if child is Button and child.get_meta("instance_ref", "") == first.arguments.card_id:
			card = child
	if card == null:
		_smoke_fail("visible card button")
		return
	await _click(card.get_global_rect().get_center())
	if model.selected_card != first.arguments.card_id:
		_smoke_fail("native card click")
		return
	var point = board._box(model.entry(first.arguments.space_id).box).get_center()
	await _click(board.get_global_transform() * point)
	if model.selected_space != first.arguments.space_id:
		_smoke_fail("native board click")
		return
	for attempt in range(100):
		if api.image_workers == 0:
			break
		await get_tree().create_timer(0.1).timeout
	await _capture("selected")
	_set_tab("market")
	for attempt in range(100):
		if api.image_workers == 0:
			break
		await get_tree().create_timer(0.1).timeout
	await _capture("market")
	print("GODOT_CAPTURE_OK")
	await _quit_cleanly()


func _click(point: Vector2) -> void:
	for pressed in [true, false]:
		var event = InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		event.position = get_viewport().get_final_transform() * point
		event.global_position = event.position
		Input.parse_input_event(event)
		await get_tree().process_frame


func _capture(name: String) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	if name == "selected":
		var pane = content.get_parent().get_global_rect()
		var visible_actions = 0
		for node in content.get_children():
			if node is Button and pane.intersects(node.get_global_rect()):
				visible_actions += 1
		if visible_actions == 0 or finish_button.get_global_rect().position.y < pane.end.y:
			_smoke_fail("selected action visibility or overlap")
			return
	var image = get_viewport().get_texture().get_image()
	var error = image.save_png(capture_dir.path_join(name + ".png"))
	if error != OK:
		_smoke_fail("save capture")
