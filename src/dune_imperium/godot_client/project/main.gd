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
var playthrough_seeds = ""
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
var load_button: Button
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
		elif argument.begins_with("--playthrough="):
			playthrough_seeds = argument.trim_prefix("--playthrough=")
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
		load_button.disabled = false
		status.text = "새 게임을 눌러 출발하세요"
		if model.catalog.get("board_image") != null:
			board.board_texture = api.texture(str(model.catalog.board_image))
		board.queue_redraw()
	else:
		status.text = "서버에 연결하지 못했습니다. 다시 실행해 주세요."
	if not playthrough_seeds.is_empty():
		var runner = load("res://playthrough.gd").new()
		add_child(runner)
		runner.run(self, playthrough_seeds)
	elif smoke:
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
	load_button = _button(header, "이어하기", _show_saves)
	load_button.disabled = true
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
	selection.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	selection.custom_minimum_size.y = 28
	var side = _panel(middle)
	side.custom_minimum_size.x = 360
	var stack = VBoxContainer.new()
	side.add_child(stack)
	var tabs = HBoxContainer.new()
	stack.add_child(tabs)
	for item in [["choices", "선택"], ["market", "시장"], ["table", "테이블"], ["log", "기록"]]:
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
	status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	status.add_theme_color_override("font_color", Color("9caebc"))


func _clear(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()


func _new_game() -> void:
	if busy:
		return
	var dialog = ConfirmationDialog.new()
	dialog.title = "새 기본 봉기 게임"
	dialog.dialog_text = ""
	dialog.ok_button_text = "게임 시작"
	dialog.cancel_button_text = "취소"
	dialog.theme = theme
	var body = VBoxContainer.new()
	body.custom_minimum_size = Vector2(420, 110)
	dialog.add_child(body)
	_label(body, "나 + 앱 AI 어려움 3명으로 시작합니다.", 16)
	var draft = CheckBox.new()
	draft.text = "지도자 공개 드래프트"
	body.add_child(draft)
	add_child(dialog)
	dialog.confirmed.connect(func(): _create_game(null, draft.button_pressed); dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered(Vector2i(420, 180))


func _create_game(seed: Variant, draft = false, pace = "fast") -> bool:
	if busy or model.catalog.is_empty():
		return false
	busy = true
	generation += 1
	status.text = "아라키스로 떠나는 중…"
	_lock_controls()
	var result = await api.call_json(HTTPClient.METHOD_POST, "/games", {"seats": ["human", "app_ai", "app_ai", "app_ai"], "game_seed": seed, "ai_pace": pace, "leader_draft": draft})
	if not _accept(result):
		busy = false
		_render()
		return false
	var accepted = await _adopt_game(str(result.data.game_id))
	busy = false
	_render()
	return accepted


func _adopt_game(id: String) -> bool:
	game_id = id
	model.adopt({})
	inspect_ref = ""
	tab = "choices"
	board.reset_view()
	return await _sync()


func _accept(reply: Dictionary) -> bool:
	if reply.ok:
		return true
	var detail = reply.data.get("detail", "연결이 끊겼습니다. 다시 시도해 주세요.") if reply.data is Dictionary else "서버 응답을 읽지 못했습니다."
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
		if model.summary().get("finished", false):
			tab = "choices"
		_render()
	return true


func _render() -> void:
	var summary = model.summary()
	var view = model.view()
	new_button.disabled = busy
	load_button.disabled = busy
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
		var who = model.seat_name(seat)
		var leader_name = model.name_of(str(player.leader_id)) if player.leader_id != null else "지도자 선택 대기"
		var leader = _label(stack, "%s · %s" % [who, leader_name], 15)
		leader.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		var resources = player.get("resources", {})
		_label(stack, "%d점    솔라리 %d  ·  스파이스 %d  ·  물 %d" % [int(player.victory_points), int(resources.get("solari", 0)), int(resources.get("spice", 0)), int(resources.get("water", 0))], 14)
		_label(stack, "에이전트 %d  ·  수비대 %d  ·  전투력 %d  ·  책략 %d" % [int(player.agents_available), int(player.troops_garrison), int(player.combat_strength), int(player.intrigue_card_count)], 13)
		_label(stack, "전투: 병력 %d · 모래벌레 %d%s" % [int(player.troops_conflict), int(player.sandworms_conflict), "  /  공개 완료" if player.has_revealed else ""], 13)
		if player.leader_id != null:
			panel.mouse_entered.connect(_inspect.bind(str(player.leader_id)))
			panel.gui_input.connect(func(event):
				if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
					_open_details(str(player.leader_id))
			)
	_clear(hand)
	images = images.filter(func(image): return is_instance_valid(image))
	var private = view.get("private", {})
	var hand_cards = private.get("hand", [])
	var intrigues = private.get("intrigue_cards", [])
	own_line.text = "내 손패  %d장    /    책략 %d장" % [hand_cards.size(), intrigues.size()]
	var decision = summary.get("decision")
	if decision is Dictionary and decision.get("persuasion") != null:
		own_line.text += "    /    남은 설득력 %d" % int(decision.persuasion)
	for ref in hand_cards:
		_card(hand, ref, 124, 164)
	if not intrigues.is_empty():
		var separator = VSeparator.new()
		hand.add_child(separator)
		for ref in intrigues:
			_card(hand, ref, 114, 164)
	board.refresh()
	board.conflict_texture = null
	board.set_meta("conflict_path", "")
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
	elif summary.get("confirmation") == 0:
		status.text = "남은 선택을 해결했습니다. 턴 종료로 확정하세요."
	elif decision is Dictionary and int(decision.get("owner", -1)) == 0:
		status.text = "내 차례 · " + model.prompt()
	else:
		status.text = "카드를 고르고 보드의 칸을 선택하세요. 배치 후 남은 효과를 해결하면 턴을 끝낼 수 있습니다."


func _lock_controls() -> void:
	new_button.disabled = true
	load_button.disabled = true
	save_button.disabled = true
	undo_button.disabled = true
	finish_button.disabled = true
	for node in content.get_children():
		if node is Button:
			node.disabled = true


func _image_path(entry: Dictionary) -> String:
	var value = model.localized(entry, "image")
	return str(value) if value != null else ""


func _card(parent: Node, ref: String, width: int, height: int, playable = true) -> void:
	var button = Button.new()
	button.custom_minimum_size = Vector2(width, height)
	button.tooltip_text = model.name_of(ref)
	button.set_meta("instance_ref", ref)
	button.pressed.connect(_choose_ref.bind(ref) if playable else _open_details.bind(ref))
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
			_choose_ref_action(ref)
			return
		tab = "choices"
		_render()
	else:
		_choose_ref_action(ref)


func _choose_ref_action(ref: String) -> void:
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
	button.set_meta("action_index", int(action.index))
	button.disabled = busy
	for value in action.get("arguments", {}).values():
		if value is String and not model.entry(value).is_empty():
			button.mouse_entered.connect(_inspect.bind(value))
			button.gui_input.connect(func(event):
				if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
					_open_details(value)
			)
			break
	if int(model.held_action().get("index", -1)) == int(action.index):
		button.add_theme_stylebox_override("normal", _style(Color("53442f"), Color("e1bd7c")))


func _render_choices(filtered: Array = []) -> void:
	_clear(content)
	finish_button.disabled = true
	finish_button.text = model.finish_text()
	selection.text = "카드와 칸을 선택해 에이전트를 보내세요" if not model.placements().is_empty() else model.prompt()
	if not model.selected_card.is_empty():
		selection.text = model.name_of(model.selected_card) + "  →  " + (model.name_of(model.selected_space) if not model.selected_space.is_empty() else "칸을 선택하세요")
	var held = model.held_action()
	if not held.is_empty():
		finish_button.disabled = busy
	elif model.summary().get("confirmation") == 0:
		finish_button.disabled = busy
	else:
		finish_button.disabled = busy or model.finish_action().is_empty()
	if tab == "market":
		_render_market()
		return
	if tab == "log":
		_render_log()
		return
	if tab == "table":
		_render_table()
		return
	if model.summary().get("finished", false):
		_render_results()
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
	var decision = model.summary().get("decision")
	if decision is Dictionary and decision.get("persuasion") != null:
		_label(content, "남은 설득력 %d" % int(decision.persuasion), 20)
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


func _render_results() -> void:
	_label(content, "게임 종료 · 최종 순위", 22)
	for standing in model.summary().get("standings", []):
		var seat = int(standing.player)
		var body = VBoxContainer.new()
		var panel = _panel(content)
		panel.add_child(body)
		_label(body, "%d위 · %s · %d점" % [int(standing.rank), model.seat_name(seat), int(standing.victory_points)], 20)
		_label(body, "스파이스 %d · 솔라리 %d · 물 %d\n수비대 %d" % [int(standing.spice), int(standing.solari), int(standing.water), int(standing.troops_garrison)], 14)
	_label(content, "순위와 동점 결과는 Python 서버의 최종 판정입니다. 테이블에서 각자의 카드를 다시 볼 수 있습니다.", 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _render_table() -> void:
	_label(content, "현재 교전", 20)
	for ref in model.view().get("current_conflict_ids", []):
		_button(content, model.name_of(ref) + " · 보상 보기", _open_details.bind(ref))
	_label(content, "방어벽: " + ("있음" if model.view().get("shield_wall_present", true) else "파괴됨"), 14)
	for player in model.view().get("players", []):
		var who = model.seat_name(int(player.player))
		var leader_name = model.name_of(str(player.leader_id)) if player.leader_id != null else "지도자 선택 대기"
		_label(content, who + " · " + leader_name, 19)
		if player.leader_id != null:
			_button(content, "지도자 능력 보기", _open_details.bind(str(player.leader_id)))
		var tracks: PackedStringArray = []
		for faction in player.get("influence", {}):
			tracks.append("%s %d" % [model.name_of(faction), int(player.influence[faction])])
		_label(content, " / ".join(tracks), 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		for flags in [["alliance_faction_ids", "동맹"], ["control_space_ids", "지배"]]:
			var names: PackedStringArray = []
			for ref in player.get(flags[0], []):
				names.append(model.name_of(str(ref)))
			_label(content, flags[1] + ": " + (" / ".join(names) if not names.is_empty() else "없음"), 14)
		_label(content, "스파이: 보급 %d · 보드 %d · 배치 대기 %d\n병력: 보급 %d · 수비대 %d · 교전 %d\n모래벌레 %d · 전투력 %d" % [int(player.spies_supply), player.spy_post_ids.size(), int(player.get("track_spies_owed", 0)), int(player.troops_supply), int(player.troops_garrison), int(player.troops_conflict), int(player.sandworms_conflict), int(player.combat_strength)], 14)
		for group in [["in_play", "플레이한 카드"], ["discard_pile", "버린 카드"], ["trashed", "폐기한 카드"], ["intrigue_faceup", "공개된 책략"], ["objective_ids", "목표"], ["won_conflict_ids", "승리한 교전"], ["face_down_battle_card_ids", "뒤집힌 전투 카드"]]:
			var refs = player.get(group[0], [])
			_button(content, "%s · %d장" % [group[1], refs.size()], _open_pile.bind(who + " · " + group[1], refs))
		if int(player.player) == 0:
			var deck = model.view().get("private", {}).get("deck_cards", [])
			_button(content, "내 덱 구성 · %d장" % deck.size(), _open_pile.bind("내 덱 구성 · 순서 비공개", deck))
		else:
			_label(content, "손패 %d장 · 덱 %d장" % [int(player.hand_size), int(player.deck_size)], 14)
	_button(content, "책략 버린 더미", _open_pile.bind("책략 버린 더미", model.view().get("intrigue_discard", [])))


func _open_pile(title: String, refs: Array) -> AcceptDialog:
	var dialog = AcceptDialog.new()
	dialog.title = title
	dialog.ok_button_text = "닫기"
	dialog.theme = theme
	var root = VBoxContainer.new()
	root.custom_minimum_size = Vector2(620, 460)
	dialog.add_child(root)
	var body = _scroll(root)
	if refs.is_empty():
		_label(body, "카드가 없습니다.", 18)
	for index in range(0, refs.size(), 3):
		var row = HBoxContainer.new()
		body.add_child(row)
		for offset in range(mini(3, refs.size() - index)):
			var ref = str(refs[index + offset])
			_card(row, ref, 186, 246, false)
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()
	return dialog


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
		parts.append("공개: 설득력 %d · 검 %d" % [int(entry.get("persuasion", 0)), int(entry.get("swords", 0))])
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
	var rewards = model.localized(entry, "rewards")
	if rewards is Array:
		for index in range(rewards.size()):
			parts.append("%d위: %s" % [index + 1, model.phrase(rewards[index])])
	if entry.get("icon") != null:
		parts.append("전투 아이콘: " + model.name_of(str(entry.icon)))
	var notes = model.localized(entry, "notes")
	if notes is Array:
		for line in notes:
			parts.append(model.phrase(line))
	return "\n\n".join(parts)


func _update_inspector() -> void:
	if inspect_ref.is_empty():
		inspector_title.text = "테이블을 살펴보세요"
		inspector_words.text = "카드·칸·선택 버튼에 마우스를 올리면 자세히 볼 수 있습니다. 오른쪽 클릭으로 큰 그림과 설명을 엽니다."
		inspector_image.set_meta("image_path", "")
		inspector_image.texture = null
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
	_lock_controls()
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/actions", model.request_body(action))
	var accepted = _accept(reply)
	tab = "choices"
	await _sync()
	busy = false
	_render()
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
		var action = model.finish_action()
		if not action.is_empty():
			await _send_action(action)


func _mutate(path: String, extra: Dictionary) -> bool:
	if busy:
		return false
	busy = true
	generation += 1
	_lock_controls()
	var data = {"seat": 0, "revision": int(model.summary().revision), "undo_count": int(model.summary().undo_count)}
	data.merge(extra)
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/" + path, data)
	var accepted = _accept(reply)
	await _sync()
	busy = false
	_render()
	return accepted


func _undo() -> void:
	await _mutate("undo", {"steps": 1})


func _save() -> void:
	var reply = await _save_game()
	if reply.get("ok", false):
		status.text = "현재 판을 저장했습니다. 이어하기에서 다시 열 수 있습니다."


func _save_game() -> Dictionary:
	if game_id.is_empty() or busy:
		return {"ok": false}
	busy = true
	_lock_controls()
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/save", {"name": "Godot 시제품"})
	busy = false
	_accept(reply)
	_render()
	return reply


func _show_saves() -> AcceptDialog:
	if busy:
		return null
	busy = true
	_lock_controls()
	var reply = await api.call_json(HTTPClient.METHOD_GET, "/saves")
	busy = false
	_render()
	if not _accept(reply) or not reply.data is Array:
		return null
	var dialog = AcceptDialog.new()
	dialog.title = "저장한 기본 봉기 게임 이어하기"
	dialog.ok_button_text = "닫기"
	dialog.theme = theme
	var root = VBoxContainer.new()
	root.custom_minimum_size = Vector2(600, 440)
	dialog.add_child(root)
	var body = _scroll(root)
	_label(body, "사람 1명(첫 좌석) + AI 3명의 기본판 저장을 열 수 있습니다.", 15).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var count = 0
	for saved in reply.data:
		if not model.supported_save(saved):
			continue
		count += 1
		var title = "자동 저장" if saved.get("autosave", false) else str(saved.get("name", "저장한 게임"))
		var button = _button(body, "%s · %d 라운드 · %s\n%s" % [title, int(saved.get("round_number", 0)), "종료" if saved.get("finished", false) else model.label("PHASE_LABELS", str(saved.get("phase", ""))), str(saved.get("saved_at", ""))], func():
			dialog.hide()
			_load_game(str(saved.save_id))
			dialog.queue_free()
		)
		button.set_meta("save_id", str(saved.save_id))
	if count == 0:
		_label(body, "이 시제품에서 이어할 저장이 없습니다.", 18)
	add_child(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()
	return dialog


func _load_game(save_id: String) -> bool:
	if busy:
		return false
	busy = true
	generation += 1
	_lock_controls()
	status.text = "저장한 판을 복원하고 있습니다…"
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/saves/" + save_id.uri_encode() + "/load")
	if not _accept(reply):
		busy = false
		_render()
		return false
	var accepted = await _adopt_game(str(reply.data.game_id))
	busy = false
	_render()
	return accepted


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
	_set_tab("table")
	await _capture("tableau")
	var pile = _open_pile("내 손패 · 살펴보기", model.view().get("private", {}).get("hand", []))
	await _capture("pile")
	pile.confirmed.emit()
	await get_tree().process_frame
	await _click(new_button.get_global_rect().get_center())
	await _capture("new-game")
	var draft_dialog: ConfirmationDialog
	for child in get_children():
		if child is ConfirmationDialog:
			draft_dialog = child
	if draft_dialog == null:
		_smoke_fail("new game dialog did not open")
		return
	var draft: CheckBox
	for child in draft_dialog.find_children("*", "CheckBox", true, false):
		draft = child
	if draft == null:
		_smoke_fail("draft setting absent")
		return
	await _click(Vector2(draft_dialog.position) + draft.get_global_rect().get_center())
	if not draft.button_pressed:
		_smoke_fail("draft checkbox click")
		return
	await _click(Vector2(draft_dialog.position) + draft_dialog.get_ok_button().get_global_rect().get_center())
	while busy or refreshing:
		await get_tree().process_frame
	if not model.summary().get("leader_draft", false):
		_smoke_fail("draft game did not start from dialog")
		return
	if inspector_image.texture != null or inspector_title.text != "테이블을 살펴보세요":
		_smoke_fail("new game kept another game's inspector")
		return
	await _capture("draft")
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
