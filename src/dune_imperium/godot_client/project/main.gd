extends Control

const Api = preload("res://api.gd")
const Model = preload("res://model.gd")
const Board = preload("res://board.gd")
const Doorbell = preload("res://doorbell.gd")
const SessionTools = preload("res://session_tools.gd")
const ChoicePresenter = preload("res://choices.gd")
const ExpansionPresenter = preload("res://expansions.gd")
const Portrait = preload("res://portrait.gd")
const DetailEntry = preload("res://detail_entry.gd")
const ActionChoice = preload("res://action_choice.gd")
const FrontMenu = preload("res://front_menu.gd")

var api = Api.new()
var doorbell = Doorbell.new()
var tools_ui = SessionTools.new()
var choices = ChoicePresenter.new()
var expansions = ExpansionPresenter.new()
var model = Model.new()
var log_ui = preload("res://log_presenter.gd").new()
var layout_ui = preload("res://layout_preferences.gd").new()
var display_ui = preload("res://display_scale.gd").new()
var effects = preload("res://table_effects.gd").new()
var feedback = preload("res://action_feedback.gd").new()
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
var playthrough_rules = ""
var poll_timer: Timer

var status: Label
var pointer_hint: Label
var preview_hint: Label
var round_label: Label
var turn_label: Label
var seats: VBoxContainer
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
var market_content: VBoxContainer
var log_content: VBoxContainer
var seat_scroll: ScrollContainer
var side_stack: VBoxContainer
var market_scroll: ScrollContainer
var preview: PanelContainer
var hover_source: Control
var hover_serial = 0
var hand_panel: PanelContainer
var hand_scroll: ScrollContainer
var board_tools: HBoxContainer
var table_surface: Control
var front_ui: Control
var host_control = ""
var menu_test = false


func _ready() -> void:
	var credentials: Dictionary = {}
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--server="):
			api.base_url = argument.trim_prefix("--server=").trim_suffix("/")
		elif argument.begins_with("--labels="):
			var file = FileAccess.open(argument.trim_prefix("--labels="), FileAccess.READ)
			if file != null:
				var parsed = JSON.parse_string(file.get_as_text())
				if parsed is Dictionary:
					model.words = parsed
		elif argument.begins_with("--host-control="):
			host_control = argument.trim_prefix("--host-control=")
		elif argument == "--smoke":
			smoke = true
		elif argument == "--menu-test":
			menu_test = true
		elif argument.begins_with("--capture="):
			capture_dir = argument.trim_prefix("--capture=")
		elif argument.begins_with("--rules="):
			playthrough_rules = argument.trim_prefix("--rules=")
		elif argument.begins_with("--playthrough="):
			playthrough_seeds = argument.trim_prefix("--playthrough=")
		elif argument.begins_with("--test-profile="):
			var profile = argument.trim_prefix("--test-profile=")
			tools_ui.prefs_file = profile + "-ui.json"
			api.cookie_file = profile + "-cookies.json"
		elif argument.begins_with("--host-credentials="):
			var path = argument.trim_prefix("--host-credentials=")
			var data = JSON.parse_string(FileAccess.get_file_as_string(path))
			DirAccess.remove_absolute(path)
			if data is Dictionary:
				credentials = data
	if get_meta("menu_test_guest", false):
		menu_test = false
		capture_dir = ""
		playthrough_seeds = ""
		smoke = false
	choices.table = self
	log_ui.table = self
	add_child(display_ui)
	display_ui.setup(get_window())
	_build_theme()
	_build_table()
	add_child(api)
	if credentials.get("origin") == api.base_url and credentials.get("key") is String:
		await api.call_json(HTTPClient.METHOD_POST, "/auth/admin", {"key": credentials.key})
	credentials.clear()
	doorbell.api = api
	add_child(doorbell)
	doorbell.changed.connect(_poll)
	doorbell.closed.connect(func(): tools_ui.leave_game())
	add_child(tools_ui)
	await tools_ui.setup(self)
	_refresh_chrome(self)
	layout_ui.setup(self)
	add_child(expansions)
	expansions.setup(self)
	add_child(effects)
	effects.setup(self)
	api.texture_ready.connect(_texture_ready)
	var timer = Timer.new()
	poll_timer = timer
	timer.wait_time = 0.8
	timer.timeout.connect(_poll)
	add_child(timer)
	timer.start()
	get_tree().auto_accept_quit = false
	if not api.base_url.is_empty():
		var catalog = await api.call_json(HTTPClient.METHOD_GET, "/catalog")
		if catalog.ok:
			model.catalog = catalog.data
			new_button.disabled = not model.server_info.get("admin", true)
			load_button.disabled = not model.server_info.get("admin", true)
			status.text = model.native("새 게임을 눌러 출발하세요")
			if model.catalog.get("board_image") != null:
				board.board_texture = api.texture(str(model.catalog.board_image))
			board.queue_redraw()
		else:
			status.text = model.native("서버에 연결하지 못했습니다. 다시 실행해 주세요.")
	front_ui = FrontMenu.new()
	add_child(front_ui)
	front_ui.setup(self, host_control)
	if not menu_test and (smoke or not capture_dir.is_empty() or not playthrough_seeds.is_empty()):
		front_ui.show_table()
	if menu_test:
		var runner = load("res://front_menu_test.gd").new()
		add_child(runner)
		runner.run(self)
	elif not playthrough_seeds.is_empty():
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
	theme.default_font_size = 14
	theme.set_color("font_color", "Label", Color("efe9dd"))
	theme.set_color("font_color", "Button", Color("efe9dd"))
	theme.set_color("font_hover_color", "Button", Color.WHITE)
	theme.set_color("font_disabled_color", "Button", Color("747d85"))
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var style = _style(Color("252b2d"), Color("555044"))
		if state == "hover":
			style.bg_color = Color("38352c")
			style.border_color = Color("d9b67e")
		elif state == "pressed":
			style.bg_color = Color("4b4031")
			style.border_color = Color("e5bf7d")
		elif state == "disabled":
			style.bg_color = Color("1b232a")
		theme.set_stylebox(state, "Button", style)
	theme.set_stylebox("panel", "AcceptDialog", _style(Color("1b1f21")))
	for key in ["embedded_border", "embedded_unfocused_border"]:
		var border = ThemeDB.get_default_theme().get_stylebox(key, "Window").duplicate()
		border.bg_color = Color("252b2d")
		border.border_color = Color("394043")
		theme.set_stylebox(key, "Window", border)
	theme.set_constant("separation", "VBoxContainer", 10)
	theme.set_constant("separation", "HBoxContainer", 10)


func _style(background: Color, border: Color = Color("35414b")) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	return style


func _panel(parent: Node, padding = 12) -> PanelContainer:
	var panel = PanelContainer.new()
	var style = _style(Color("1b1f21"))
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
	_native_meta(label, text)
	label.add_theme_font_size_override("font_size", font_size)
	parent.add_child(label)
	return label


func _button(parent: Node, text: String, callback: Callable) -> Button:
	var button = Button.new()
	button.text = text
	_native_meta(button, text)
	button.custom_minimum_size.y = 42
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _compact_button(button: Button) -> void:
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var compact = button.get_theme_stylebox(state).duplicate()
		compact.content_margin_left = 6
		compact.content_margin_right = 6
		button.add_theme_stylebox_override(state, compact)


func _native_meta(node: Node, text: String) -> void:
	if Model.NativeText.EN.has(text):
		node.set_meta("native_text", text)
	elif text in Model.NativeText.EN.values():
		node.set_meta("native_text", Model.NativeText.EN.find_key(text))


func _refresh_chrome(node: Node) -> void:
	if node.has_meta("native_text"):
		node.text = model.native(node.get_meta("native_text"))
	for child in node.get_children():
		_refresh_chrome(child)


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
	table_surface = margin
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for key in ["margin_left", "margin_right", "margin_top", "margin_bottom"]:
		margin.add_theme_constant_override(key, 8)
	add_child(margin)
	var root = VBoxContainer.new()
	root.add_theme_constant_override("separation", 8)
	margin.add_child(root)
	var header = HBoxContainer.new()
	root.add_child(header)
	_label(header, "Dune: Imperium — Uprising", 18).add_theme_color_override("font_color", Color("d5b478"))
	var context = VBoxContainer.new()
	context.add_theme_constant_override("separation", 2)
	context.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(context)
	round_label = _label(context, "", 12)
	round_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	round_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	round_label.add_theme_color_override("font_color", Color("a8b3bd"))
	turn_label = _label(context, "", 15)
	turn_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	turn_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	new_button = _button(header, model.native("새 게임"), _new_game)
	new_button.disabled = true
	load_button = _button(header, model.native("이어하기"), _show_saves)
	load_button.disabled = true
	save_button = _button(header, model.native("저장"), _save)
	save_button.disabled = true
	undo_button = _button(header, model.native("되돌리기"), _undo)
	undo_button.disabled = true
	for button in [new_button, load_button, save_button, undo_button]:
		button.custom_minimum_size.y = 34
	var table = HBoxContainer.new()
	table.size_flags_vertical = Control.SIZE_EXPAND_FILL
	table.add_theme_constant_override("separation", 8)
	root.add_child(table)
	seat_scroll = ScrollContainer.new()
	seat_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	table.add_child(seat_scroll)
	seats = VBoxContainer.new()
	seats.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	seats.add_theme_constant_override("separation", 8)
	seat_scroll.add_child(seats)
	var center = HBoxContainer.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center.add_theme_constant_override("separation", 8)
	table.add_child(center)
	var board_column = VBoxContainer.new()
	board_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center.add_child(board_column)
	board = Board.new()
	board.model = model
	board.api = api
	board.size_flags_vertical = Control.SIZE_EXPAND_FILL
	board.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board.custom_minimum_size = Vector2(300, 280)
	board.chosen.connect(_choose_ref)
	board.inspected.connect(func(ref): _pointed(ref, board))
	board.details_requested.connect(_open_details)
	board_column.add_child(board)
	hand_panel = _panel(board_column, 6)
	var hand_stack = VBoxContainer.new()
	hand_stack.add_theme_constant_override("separation", 4)
	hand_panel.add_child(hand_stack)
	var hand_heading = HBoxContainer.new()
	hand_stack.add_child(hand_heading)
	own_line = _label(hand_heading, model.native("내 손패"), 14)
	own_line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	own_line.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	board_tools = HBoxContainer.new()
	hand_heading.add_child(board_tools)
	var reset = _button(board_tools, model.native("전체 보기"), _reset_board)
	reset.custom_minimum_size.y = 28
	reset.tooltip_text = model.native("휠: 확대·축소 / 가운데 버튼 드래그: 이동")
	var deck_button = _button(hand_heading, model.native("덱"), func(): _open_pile(model.native("내 덱 구성 · 순서 비공개"), model.view().get("private", {}).get("deck_cards", []), false, ["private", "deck_cards"]))
	deck_button.custom_minimum_size.y = 26
	hand_scroll = ScrollContainer.new()
	hand_scroll.custom_minimum_size.y = 190
	hand_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	hand_stack.add_child(hand_scroll)
	hand = HBoxContainer.new()
	hand.add_theme_constant_override("separation", 6)
	hand_scroll.add_child(hand)
	hand_scroll.resized.connect(_size_table_cards)
	var shared_panel = _panel(center, 6)
	market_scroll = ScrollContainer.new()
	market_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	shared_panel.add_child(market_scroll)
	market_content = VBoxContainer.new()
	market_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	market_content.add_theme_constant_override("separation", 6)
	market_scroll.add_child(market_content)
	side_stack = VBoxContainer.new()
	side_stack.add_theme_constant_override("separation", 8)
	table.add_child(side_stack)
	var side = _panel(side_stack, 10)
	side.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var stack = VBoxContainer.new()
	side.add_child(stack)
	var tabs = HBoxContainer.new()
	stack.add_child(tabs)
	for item in [["choices", model.native("현재 선택")], ["table", model.native("테이블 상세")]]:
		var button = _button(tabs, item[1], _set_tab.bind(item[0]))
		button.custom_minimum_size.y = 30
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	selection = _label(stack, model.native("카드를 선택하세요"), 18)
	selection.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	selection.add_theme_color_override("font_color", Color("e8c78a"))
	content = _scroll(stack)
	finish_button = _button(stack, model.native("턴 종료 ▶"), _finish)
	finish_button.custom_minimum_size.y = 46
	finish_button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	finish_button.add_theme_font_size_override("font_size", 18)
	finish_button.add_theme_stylebox_override("normal", _style(Color("514330"), Color("d7b178")))
	finish_button.add_theme_stylebox_override("hover", _style(Color("705936"), Color("f1d39b")))
	finish_button.add_theme_stylebox_override("pressed", _style(Color("8a6839"), Color("f1d39b")))
	finish_button.disabled = true
	var history = _panel(side_stack, 8)
	var history_stack = VBoxContainer.new()
	history_stack.custom_minimum_size.y = 180
	history.add_child(history_stack)
	var history_header = HBoxContainer.new()
	history_stack.add_child(history_header)
	_label(history_header, model.native("행동 기록"), 14).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var full_log = _button(history_header, model.native("전체 기록"), _set_tab.bind("log"))
	full_log.custom_minimum_size.y = 24
	full_log.add_theme_font_size_override("font_size", 11)
	full_log.set_meta("full_log", true)
	_compact_button(full_log)
	feedback.setup(self, history_stack)
	log_content = _scroll(history_stack)
	status = _label(root, model.native("테이블을 준비하고 있습니다…"), 12)
	status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	status.add_theme_color_override("font_color", Color("9caebc"))
	pointer_hint = _label(root, "", 12)
	pointer_hint.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	pointer_hint.hide()
	_build_preview()
	resized.connect(_fit_columns)
	_fit_columns()


func _fit_columns() -> void:
	# Match the browser's three main columns, with shared cards beside the board.
	var widths = layout_ui.widths() if layout_ui.table != null else {"seats": 210 if size.x >= 1340 else 172, "choices": 320 if size.x >= 1340 else 280, "market": 176 if size.x >= 1340 else 160}
	seat_scroll.custom_minimum_size.x = widths.seats
	side_stack.custom_minimum_size.x = widths.choices
	market_scroll.custom_minimum_size.x = widths.market
	_size_table_cards()
	for window in find_children("*", "Window", true, false):
		if window.visible and not window.is_queued_for_deletion():
			var extent = Vector2i(size) - window.size
			window.position = Vector2i(clampi(window.position.x, 8, maxi(8, extent.x - 8)), clampi(window.position.y, 32, maxi(32, extent.y - 8)))
	_hide_preview()


func _size_table_cards() -> void:
	if hand_scroll == null:
		return
	var dimensions = Vector2(144, 238) if size.y >= 980 else Vector2(128, 214) if size.y >= 840 else Vector2(112, 184)
	# Keep a normal five-card hand in view when the board column can fit it.
	# Larger hands continue to scroll rather than shrinking below 112 pixels.
	if hand_scroll.size.x > 0:
		dimensions.x = clampf(floorf((hand_scroll.size.x - 24) / 5), 112, dimensions.x)
	hand_scroll.visible = hand.get_child_count() > 0
	hand_scroll.custom_minimum_size.y = dimensions.y + 12 if hand_scroll.visible else 0
	for card in hand.get_children():
		if card.has_meta("table_card"):
			card.custom_minimum_size = dimensions if card.get_meta("table_card") == "hand" else dimensions * 0.9
	var width = maxi(68, floori((market_scroll.custom_minimum_size.x - 12) / 2))
	for card in market_content.find_children("*", "Button", true, false):
		if card.get_meta("table_card", "") == "market":
			card.custom_minimum_size = Vector2(width, width * 1.42 + 42)
		elif card.get_meta("table_card", "") == "landscape":
			var landscape_width = maxi(138, int(market_scroll.custom_minimum_size.x) - 8)
			card.custom_minimum_size = Vector2(landscape_width, floori(landscape_width * 0.62) + 42)
	for item in market_content.get_children():
		if item.has_meta("market_research"):
			var board_width = maxi(138, int(market_scroll.custom_minimum_size.x) - 8)
			item.custom_minimum_size = Vector2(board_width, floori(board_width * 0.71))


func _build_preview() -> void:
	preview = _panel(self, 12)
	preview.z_index = 20
	preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var row = HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	preview.add_child(row)
	inspector_image = Portrait.new()
	inspector_image.model = model
	inspector_image.custom_minimum_size = Vector2(265, 372)
	inspector_image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	inspector_image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	inspector_image.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(inspector_image)
	var body = VBoxContainer.new()
	body.custom_minimum_size.x = 275
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(body)
	inspector_title = _label(body, "", 20)
	inspector_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector_title.max_lines_visible = 2
	inspector_title.add_theme_color_override("font_color", Color("e8c78a"))
	inspector_words = _label(body, "", 15)
	inspector_words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector_words.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspector_words.clip_text = true
	preview_hint = _label(body, "", 13)
	preview_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	preview_hint.max_lines_visible = 3
	_label(body, model.native("오른쪽 클릭: 상세 보기"), 12).add_theme_color_override("font_color", Color("a9a69b"))
	_ignore_mouse(preview)
	preview.hide()


func _ignore_mouse(node: Node) -> void:
	if node is Control:
		node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for child in node.get_children():
		_ignore_mouse(child)


func _bind_preview(control: Control, ref: String) -> void:
	control.set_meta("preview_ref", ref)
	if control is Label:
		control.mouse_filter = Control.MOUSE_FILTER_PASS
	control.mouse_entered.connect(_pointed.bind(ref, control))
	control.mouse_exited.connect(_hide_preview)
	control.gui_input.connect(func(event):
		if event is InputEventMouseMotion and event.button_mask == 0 and hover_source != control:
			_pointed(ref, control)
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
			_open_details(ref)
	)


func _pointer_allowed() -> bool:
	if busy or get_viewport().gui_is_dragging():
		return false
	# Godot's built-in tooltip is also a Window, but passes mouse input through.
	return not find_children("*", "Window", true, false).any(func(window): return window.visible and not window.mouse_passthrough and not window.is_queued_for_deletion())


func _pointed(ref: String, source: Control) -> void:
	_hide_preview(source != board or ref.is_empty())
	if ref.is_empty() or not is_instance_valid(source) or not _pointer_allowed():
		return
	hover_source = source
	var reading = model.ref_feedback(ref)
	if source.get_meta("inspect_only", false):
		reading = {"kind": "inspect", "label": model.native("살펴보기"), "hint": model.native("클릭: 상세 보기"), "name": model.name_of(ref)}
	pointer_hint.text = reading.name + " · " + reading.label + (" · " + reading.hint if not reading.hint.is_empty() else "")
	pointer_hint.tooltip_text = pointer_hint.text
	pointer_hint.add_theme_color_override("font_color", Model.REF_COLORS[reading.kind])
	pointer_hint.show()
	status.hide()
	preview_hint.text = reading.label + ("\n" + reading.hint if not reading.hint.is_empty() else "")
	preview_hint.add_theme_color_override("font_color", Model.REF_COLORS[reading.kind])
	if not model.entry(ref).is_empty():
		_hover(ref, source)


func _hover(ref: String, source: Control) -> void:
	hover_serial += 1
	var serial = hover_serial
	await get_tree().create_timer(0.22).timeout
	if serial != hover_serial or not is_instance_valid(source) or not source.is_visible_in_tree() or not _pointer_allowed():
		return
	hover_source = source
	_inspect(ref)
	preview.show()
	_place_preview()


func _place_preview() -> void:
	if not preview.visible or not is_instance_valid(hover_source):
		return
	var ratio = 0.7
	if inspector_image.texture != null:
		ratio = float(inspector_image.texture.get_width()) / inspector_image.texture.get_height()
	var landscape = ratio > 1.1
	inspector_image.custom_minimum_size = Vector2(265, floorf(minf(372, 265 / ratio)))
	inspector_words.max_lines_visible = 4 if landscape else 6
	preview.reset_size()
	preview.size = Vector2(574, 240 if landscape else 400)
	var bounds = hover_source.get_global_rect()
	if hover_source == board:
		var box = model.entry(inspect_ref).get("box")
		if box is Array:
			var region = board._box(box)
			bounds = Rect2(board.global_position + region.position, region.size)
	var point = Vector2(bounds.end.x + 12, bounds.position.y)
	if content.is_ancestor_of(hover_source) or log_content.is_ancestor_of(hover_source):
		point.x = side_stack.get_global_rect().position.x - preview.size.x - 12
	elif market_content.is_ancestor_of(hover_source):
		point.x = market_scroll.get_global_rect().position.x - preview.size.x - 12
	elif bounds.position.y > size.y * 0.65:
		point = Vector2(bounds.position.x, bounds.position.y - preview.size.y - 12)
	elif point.x + preview.size.x > size.x - 8:
		point.x = bounds.position.x - preview.size.x - 12
	var candidates = [point, Vector2(bounds.end.x + 12, bounds.position.y), Vector2(bounds.position.x - preview.size.x - 12, bounds.position.y), Vector2(bounds.position.x, bounds.position.y - preview.size.y - 12), Vector2(bounds.position.x, bounds.end.y + 12)]
	for candidate in candidates:
		var fitted = Vector2(clampf(candidate.x, 8, maxf(8, size.x - preview.size.x - 8)), clampf(candidate.y, 8, maxf(8, size.y - preview.size.y - 8)))
		preview.position = fitted
		if not Rect2(fitted, preview.size).intersects(bounds.grow(4)):
			return


func _hide_preview(clear_board = true) -> void:
	hover_serial += 1
	if clear_board and board != null:
		board.clear_hover()
	if preview != null:
		preview.hide()
	hover_source = null
	if pointer_hint != null:
		pointer_hint.text = ""
		pointer_hint.tooltip_text = ""
		pointer_hint.hide()
		status.show()
	if preview_hint != null:
		preview_hint.text = ""


func _clear(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()


func _new_game() -> void:
	tools_ui.new_game()


func _create_game(seed: Variant, draft = false, pace = "fast", options: Dictionary = {}) -> bool:
	if busy or model.catalog.is_empty():
		return false
	busy = true
	generation += 1
	status.text = model.native("아라키스로 떠나는 중…")
	_lock_controls()
	var config = {"seats": ["human", "app_ai", "app_ai", "app_ai"], "game_seed": seed, "ai_pace": pace, "leader_draft": draft}
	config.merge(options, true)
	var result = await api.call_json(HTTPClient.METHOD_POST, "/games", config)
	if not _accept(result):
		busy = false
		_render()
		return false
	var accepted = await _adopt_game(str(result.data.game_id))
	busy = false
	_render()
	return accepted


func _adopt_game(id: String) -> bool:
	tools_ui.close_game_dialogs()
	feedback.reset()
	game_id = id
	tools_ui.review.clear()
	tools_ui.playback = false
	model.adopt({})
	doorbell.start(id)
	inspect_ref = ""
	tab = "choices"
	board.reset_view()
	var accepted = await _sync()
	if accepted and front_ui != null:
		front_ui.show_table()
	if accepted and model.active_seat < 0:
		if model.summary().get("finished", false):
			await tools_ui._review_meta(0, 0, true)
		elif model.server_info.get("access") == "remote":
			tools_ui.lobby()
	return accepted


func _accept(reply: Dictionary) -> bool:
	if reply.ok:
		return true
	var detail = reply.data.get("detail", model.native("연결이 끊겼습니다. 다시 시도해 주세요.")) if reply.data is Dictionary else model.native("서버 응답을 읽지 못했습니다.")
	status.text = model.native("처리하지 못했습니다: ") + str(detail)
	return false


func _poll() -> void:
	if not closing and not busy and not refreshing and not game_id.is_empty():
		_sync()


func _sync(preferred_seat = -2) -> bool:
	while refreshing:
		await get_tree().process_frame
	if game_id.is_empty():
		return false
	refreshing = true
	var requested_game = game_id
	var requested_generation = generation
	var seat = model.active_seat if preferred_seat == -2 else preferred_seat
	var reply: Dictionary = {}
	for attempt in range(4):
		var path = "/games/" + requested_game + "/snapshot"
		if seat >= 0:
			path += "?seat=" + str(seat)
			var known = (tools_ui.live_snapshot if not tools_ui.review.is_empty() else model.snapshot).get("log")
			if known is Dictionary and int(known.get("seat", -1)) == seat:
				path += "&log_after=%d&log_epoch=%s" % [int(known.get("count", 0)), str(known.get("epoch", "")).uri_encode()]
		reply = await api.call_json(HTTPClient.METHOD_GET, path)
		if int(reply.code) == 403 and seat >= 0:
			seat = -1
			continue
		if not reply.ok:
			break
		var wanted = model.pick_seat(reply.data)
		if wanted == seat:
			break
		seat = wanted
	refreshing = false
	if requested_game != game_id or requested_generation != generation:
		return false
	if not _accept(reply):
		return false
	var data = reply.data
	if data.get("log") is Dictionary and int(data.log.get("from", 0)) > 0:
		var known = (tools_ui.live_snapshot if not tools_ui.review.is_empty() else model.snapshot).get("log", {})
		if not known is Dictionary or int(known.get("seat", -1)) != int(data.log.seat) or known.get("entries", []).size() != int(data.log.from):
			return await _sync(-1)
		data.log.entries = known.entries + data.log.entries
	tools_ui.anchor_clock(data)
	var previous_owned = model.owned_seats.duplicate()
	var previous_seat = model.active_seat
	var current_owned = data.get("you", {}).get("seats", []).map(func(value): return int(value))
	if not tools_ui.review.is_empty():
		tools_ui.live_snapshot = data.duplicate(true)
		if previous_owned.any(func(value): return value not in current_owned):
			tools_ui.playback = false
			tools_ui.review_serial += 1
			tools_ui.review.clear()
		else:
			model.owned_seats = current_owned
			model.snapshot.you = data.get("you", {})
			return true
	if int(model.summary().get("undo_count", 0)) != int(data.summary.get("undo_count", 0)):
		tools_ui.close_game_dialogs(true)
	var changed = model.adopt(data)
	if previous_seat != model.active_seat:
		tools_ui.close_game_dialogs()
		inspect_ref = ""
	for removed_seat in previous_owned:
		if removed_seat not in model.owned_seats:
			tools_ui.close_game_dialogs()
			inspect_ref = ""
			break
	if changed:
		if model.summary().get("finished", false):
			tab = "choices"
		_render()
	return true


func _render() -> void:
	_hide_preview()
	_refresh_chrome(self)
	if front_ui != null:
		front_ui.refresh_language()
	tools_ui.refresh_menu()
	var summary = model.summary()
	var view = model.view()
	new_button.disabled = busy or not model.server_info.get("admin", true)
	load_button.disabled = busy or not model.server_info.get("admin", true)
	save_button.disabled = busy or game_id.is_empty() or not model.server_info.get("admin", true)
	undo_button.disabled = busy
	if not busy:
		undo_button.disabled = true
		for item in summary.get("undo", []):
			if int(item.seat) == model.active_seat and int(item.steps) > 0 and tools_ui.review.is_empty():
				undo_button.disabled = false
	round_label.text = model.native("%d 라운드  /  %s") % [int(summary.get("round_number", 0)), model.label("PHASE_LABELS", summary.get("phase", ""))]
	var turn = model.turn_reading(not tools_ui.review.is_empty())
	turn_label.text = str(turn.symbol) + " " + (model.seat_name(turn.seat) + " · " if turn.seat >= 0 else "") + str(turn.label)
	turn_label.tooltip_text = turn_label.text
	turn_label.set_meta("turn_kind", turn.kind)
	turn_label.set_meta("turn_seat", turn.seat)
	turn_label.add_theme_color_override("font_color", Model.SEAT_COLORS[turn.seat].lightened(0.35) if turn.seat >= 0 else Color("e4c280"))
	_render_seats()
	_clear(hand)
	images = images.filter(func(image): return is_instance_valid(image))
	var private = view.get("private", {})
	var hand_cards = private.get("hand", [])
	var intrigues = private.get("intrigue_cards", [])
	own_line.text = model.native("내 손패  %d장    /    책략 %d장") % [hand_cards.size(), intrigues.size()]
	var decision = summary.get("decision")
	if decision is Dictionary and decision.get("persuasion") != null:
		own_line.text += model.native("    /    남은 설득력 %d") % int(decision.persuasion)
	for ref in layout_ui.ordered(hand_cards, "hand"):
		_card(hand, ref, 128, 214).set_meta("table_card", "hand")
	if not intrigues.is_empty():
		var separator = VSeparator.new()
		hand.add_child(separator)
		for ref in layout_ui.ordered(intrigues, "intrigue_cards"):
			_card(hand, ref, 116, 192).set_meta("table_card", "intrigue")
	hand_panel.visible = not summary.get("finished", false) or not tools_ui.review.is_empty()
	_render_market()
	expansions.render()
	_size_table_cards()
	_render_log(log_content)
	board.animations = tools_ui.prefs.get("animations", true) and not tools_ui.prefs.get("reduced_motion", false)
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
	effects.observe()
	feedback.refresh()
	for child in find_children("*", "Window", true, false):
		if child.has_meta("pile_viewer") and not child.is_queued_for_deletion():
			child.get_meta("pile_viewer").refresh()
	if summary.get("finished", false):
		status.text = model.native("게임이 끝났습니다. 승점과 최종 순위는 오른쪽에서 확인하세요.")
	elif summary.get("thinking") != null:
		status.text = model.native("앱 AI %d의 차례입니다…") % int(summary.thinking)
	elif summary.get("confirmation") == model.active_seat:
		status.text = model.native("남은 선택을 해결했습니다. 턴 종료로 확정하세요.")
	elif decision is Dictionary and int(decision.get("owner", -1)) == model.active_seat:
		status.text = model.native("내 차례 · ") + model.prompt()
	else:
		status.text = model.native("카드를 고르고 보드의 칸을 선택하세요. 배치 후 남은 효과를 해결하면 턴을 끝낼 수 있습니다.")


func _render_seats() -> void:
	_clear(seats)
	tools_ui.seat_clock_labels.clear()
	var turn = model.turn_reading(not tools_ui.review.is_empty())
	var first = model.view().get("first_player")
	if first == null and tools_ui.review.is_empty():
		first = model.summary().get("first_player")
	for player in model.view().get("players", []):
		var seat = int(player.player)
		var panel = _panel(seats, 6)
		var current = turn.seat == seat
		panel.set_meta("seat_panel", seat)
		panel.set_meta("seat_current", current)
		var style = _style(Model.SEAT_COLORS[seat].darkened(0.82) if current else Color("1b1f21"), Model.SEAT_COLORS[seat])
		style.border_width_left = 4 if current else 2
		style.border_width_top = 2 if current else 1
		style.content_margin_left = 6
		style.content_margin_right = 6
		panel.add_theme_stylebox_override("panel", style)
		var stack = VBoxContainer.new()
		stack.add_theme_constant_override("separation", 3)
		panel.add_child(stack)
		var header = HBoxContainer.new()
		stack.add_child(header)
		header.add_theme_constant_override("separation", 4)
		var seat_name = _label(header, "", 14)
		seat_name.text = model.seat_name(seat)
		seat_name.set_meta("seat_name", seat)
		seat_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		seat_name.clip_text = true
		seat_name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		seat_name.tooltip_text = seat_name.text
		var points = _button(header, model.native("%d점") % int(player.victory_points), tools_ui.vp_ledger.bind(seat))
		points.custom_minimum_size.y = 26
		points.add_theme_font_size_override("font_size", 17)
		_compact_button(points)
		points.set_meta("vp_seat", seat)
		var badges = HBoxContainer.new()
		badges.add_theme_constant_override("separation", 5)
		stack.add_child(badges)
		if current:
			var badge = _label(badges, "", 11)
			badge.text = str(turn.symbol) + " " + str(turn.label)
			badge.set_meta("seat_turn", turn.kind)
			badge.add_theme_color_override("font_color", Model.SEAT_COLORS[seat].lightened(0.45))
		var marker = model.seat_marker(seat, not tools_ui.review.is_empty())
		if not marker.is_empty():
			var badge = _label(badges, model.native("나" if marker == "owned" else "보기"), 11)
			badge.tooltip_text = model.native("내 좌석" if marker == "owned" else "보고 있는 좌석")
			badge.set_meta("seat_view", marker)
			badge.add_theme_color_override("font_color", Color("ced9e2"))
		if first != null and int(first) == seat:
			var badge = _label(badges, model.native("선"), 11)
			badge.tooltip_text = model.native("선 플레이어")
			badge.set_meta("seat_first", seat)
		var clock_spacer = Control.new()
		clock_spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		badges.add_child(clock_spacer)
		tools_ui.seat_clock_labels[seat] = _label(badges, "", 11)
		tools_ui.seat_clock_labels[seat].tooltip_text = model.ui("clock.seat_title", {"name": model.seat_name(seat)})
		tools_ui.seat_clock_labels[seat].set_meta("seat_clock", seat)
		var portrait = HBoxContainer.new()
		stack.add_child(portrait)
		if player.leader_id != null:
			var ref = str(player.get("leader_face_id") if player.get("leader_face_id") != null else player.leader_id)
			var leader = Button.new()
			leader.custom_minimum_size = Vector2(42, 56)
			leader.pressed.connect(_open_details.bind(ref))
			portrait.add_child(leader)
			var picture = _picture(leader, _image_path(model.entry(ref)), Vector2(38, 52))
			picture.position = Vector2(2, 2)
			picture.ref = ref
			_bind_preview(leader, ref)
		var info = VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		info.add_theme_constant_override("separation", 4)
		portrait.add_child(info)
		var name = model.name_of(str(player.leader_id)) if player.leader_id != null else model.native("지도자 선택 대기")
		_label(info, name, 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		var resources = HBoxContainer.new()
		resources.add_theme_constant_override("separation", 8)
		stack.add_child(resources)
		for key in ["solari", "spice", "water"]:
			_amount(resources, key, int(player.get("resources", {}).get(key, 0)))
		_label(info, model.native("에이전트 %d · 책략 %d") % [int(player.agents_available), int(player.intrigue_card_count)], 12).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		var forces = _label(stack, model.native("수비대 %d · 교전 병력 %d") % [int(player.troops_garrison), int(player.troops_conflict)], 12)
		forces.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		var strength = _label(stack, model.native("벌레 %d · 전투력 %d%s") % [int(player.sandworms_conflict), int(player.combat_strength), ""], 12)
		strength.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		if player.has_revealed:
			strength.text += " · " + model.native("공개 완료")
		strength.set_meta("seat_strength", seat)
		if tools_ui.prefs.get("seat_details", false):
			var tracks_words: PackedStringArray = []
			for faction in player.get("influence", {}):
				tracks_words.append("%s %d" % [model.name_of(faction), int(player.influence[faction])])
			_label(stack, " · ".join(tracks_words), 12).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			_label(stack, model.native("스파이 %d · 보드 %d") % [int(player.spies_supply), player.spy_post_ids.size()], 12)
		var piles = HBoxContainer.new()
		piles.add_theme_constant_override("separation", 4)
		stack.add_child(piles)
		for group in [["discard_pile", model.native("버림")], ["in_play", model.native("플레이")]]:
			var refs = player.get(group[0], [])
			var button = _button(piles, "%s %d" % [group[1], refs.size()], _open_pile.bind(model.seat_name(seat) + " · " + group[1], refs))
			button.custom_minimum_size.y = 25
			button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			button.add_theme_font_size_override("font_size", 11)
			_compact_button(button)


func _amount(parent: Node, key: String, value: int) -> void:
	var row = HBoxContainer.new()
	row.add_theme_constant_override("separation", 2)
	parent.add_child(row)
	var path = str(model.catalog.get("icons", {}).get(key, ""))
	if not path.is_empty():
		var picture = _picture(row, path, Vector2(18, 18))
		picture.tooltip_text = model.phrase("{" + key + "}")
	else:
		_label(row, model.phrase("{" + key + "}"), 12)
	var amount = _label(row, str(value), 16)
	amount.set_meta("resource_amount", key)
	amount.accessibility_name = model.phrase("{" + key + "}") + " " + str(value)
	amount.add_theme_color_override("font_color", Color("f2e4c9") if value else Color("9ba8b2"))


func _lock_controls() -> void:
	new_button.disabled = true
	load_button.disabled = true
	save_button.disabled = true
	undo_button.disabled = true
	finish_button.disabled = true
	_disable_buttons(content)


func _disable_buttons(node: Node) -> void:
	for child in node.get_children():
		if child is Button:
			child.disabled = true
		_disable_buttons(child)


func _image_path(entry: Dictionary) -> String:
	var value = model.localized(entry, "image")
	return str(value) if value != null else ""


func _picture(parent: Node, path: String, dimensions: Vector2) -> TextureRect:
	var picture = Portrait.new()
	picture.model = model
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	picture.custom_minimum_size = dimensions
	picture.size = dimensions
	picture.set_meta("image_path", path)
	picture.texture = api.texture(path)
	parent.add_child(picture)
	images.append(picture)
	return picture


func _card(parent: Node, ref: String, width: int, height: int, playable = true) -> Button:
	var button = preload("res://hand_card.gd").new()
	button.table = self
	button.ref = ref
	if parent == hand and playable:
		button.pile = "intrigue_cards" if ref in model.view().get("private", {}).get("intrigue_cards", []) else "hand"
	button.custom_minimum_size = Vector2(width, height)
	button.set_meta("instance_ref", ref)
	button.set_meta("inspect_only", not playable)
	button.pressed.connect(_choose_ref.bind(ref) if playable else _open_details.bind(ref))
	_bind_preview(button, ref)
	var reading = model.ref_feedback(ref) if playable else {"kind": "inspect", "label": "", "hint": ""}
	var kind = str(reading.kind)
	var active = kind in ["selected", "available", "partner"]
	var border = Model.REF_COLORS[kind] if kind != "inspect" else Color("3d4141")
	var background = Color("293d35") if kind == "selected" else Color("222526")
	var marker = str(reading.label) if kind != "inspect" else ""
	button.set_meta("interaction_kind", kind)
	button.mouse_default_cursor_shape = Control.CURSOR_FORBIDDEN if kind in ["unavailable", "filtered"] else Control.CURSOR_POINTING_HAND if active or not playable else Control.CURSOR_ARROW
	for state in ["normal", "hover", "pressed", "focus"]:
		var style = _style(background.lightened(0.18 if state == "pressed" else 0.08) if state in ["hover", "pressed"] else background, Color("f3eee3") if state in ["hover", "focus"] else border)
		style.set_border_width_all(3 if kind == "selected" or state == "focus" else 2 if active or state == "hover" else 1)
		button.add_theme_stylebox_override(state, style)
	parent.add_child(button)
	var entry = model.entry(ref)
	var path = _image_path(entry)
	button.face = _picture(button, path, Vector2.ZERO)
	if kind in ["unavailable", "filtered"]:
		button.face.modulate.a = 0.7
	button.tooltip_text = model.name_of(ref) + ("\n" + reading.label if not reading.label.is_empty() else "") + ("\n" + reading.hint if not reading.hint.is_empty() else "")
	button.accessibility_name = model.name_of(ref)
	button.accessibility_description = button.tooltip_text
	button.caption = _label(button, model.name_of(ref), 13 if width >= 90 else 12)
	button.caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button.caption.max_lines_visible = 2
	button.caption.clip_text = true
	button.caption.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	button.caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	button.caption.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	button.caption.set_meta("card_caption", ref)
	if path.is_empty():
		button.fallback = _label(button, _entry_words(entry, ref), 12)
		button.fallback.mouse_filter = Control.MOUSE_FILTER_IGNORE
		button.fallback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.fallback.clip_text = true
	if not marker.is_empty():
		_card_badge(button, marker, false, Model.REF_COLORS[kind])
	if model.section_id(ref)[0] == "cards" and entry.get("cost") != null:
		var cost = _card_badge(button, str(int(entry.cost)), true, Color("bee3f5"))
		cost.tooltip_text = model.native("인쇄 비용: ") + model.phrase("{persuasion:%d}" % int(entry.cost))
		button.tooltip_text += "\n" + cost.tooltip_text
	button.resized.connect(button.arrange_face)
	button.arrange_face()
	return button


func _card_badge(parent: Button, text: String, right: bool, color: Color) -> Label:
	var badge = _label(parent, text, 11)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	badge.set_meta("card_cost" if right else "card_state", text)
	badge.add_theme_color_override("font_color", color)
	var style = _style(Color("17222bed"), color.darkened(0.55))
	style.content_margin_left = 5
	style.content_margin_right = 5
	style.content_margin_top = 3
	style.content_margin_bottom = 3
	style.set_corner_radius_all(3)
	badge.add_theme_stylebox_override("normal", style)
	badge.position = Vector2(5, 5)
	if right:
		badge.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
		badge.grow_horizontal = Control.GROW_DIRECTION_BEGIN
		badge.position += Vector2(-5, 5)
	return badge


func _texture_ready(path: String, texture: Texture2D) -> void:
	board.textures[path] = texture
	board.queue_redraw()
	for picture in images:
		if is_instance_valid(picture) and picture.get_meta("image_path", "") == path:
			picture.texture = texture
			_fit_picture(picture)
	if model.catalog.get("board_image") == path:
		board.board_texture = texture
		board.queue_redraw()
	if board.get_meta("conflict_path", "") == path:
		board.conflict_texture = texture
		board.queue_redraw()
	if inspector_image.get_meta("image_path", "") == path:
		inspector_image.texture = texture
		_place_preview()


func _fit_picture(picture: TextureRect) -> void:
	var box = picture.get_meta("artwork_box", Vector2.ZERO)
	if box is Vector2 and box != Vector2.ZERO and picture.texture != null:
		var ratio = float(picture.texture.get_width()) / picture.texture.get_height()
		picture.custom_minimum_size = Vector2(box.x, floorf(minf(box.y, box.x / ratio)))


func _choose_ref(ref: String) -> void:
	_hide_preview()
	if busy:
		return
	_inspect(ref)
	if not model.placements().is_empty() and not tools_ui.prefs.get("full_action_list", false):
		var step = model.pick_step(ref)
		if step == "blocked":
			status.text = model.native("선택한 카드로는 이 칸에 갈 수 없습니다. 다른 카드나 칸을 선택하세요.")
			return
		if step == "unrelated":
			_choose_ref_action(ref)
			return
		var candidates = model.picked_placements()
		if not model.selected_card.is_empty() and not model.selected_space.is_empty() and candidates.size() == 1:
			await _apply_placement(candidates[0], model.signature())
			return
		tab = "choices"
		_render()
	else:
		_choose_ref_action(ref)


func _apply_placement(action: Dictionary, expected: String) -> void:
	if expected != model.signature() or not model.offered(action):
		return
	var partner = ""
	if not model.selected_partner.is_empty():
		partner = model.selected_partner if action.arguments.card_id == model.selected_card else model.selected_card
	var origin_game = game_id
	var origin_seat = model.active_seat
	if not await _send_action(action) or partner.is_empty():
		return
	var decision = model.summary().get("decision", {})
	if game_id != origin_game or model.active_seat != origin_seat or decision.get("kind") != "graft_partner" or int(decision.get("owner", -1)) != origin_seat:
		return
	for candidate in model.actions():
		if candidate.action_id == "choose_graft_partner" and candidate.arguments.get("card_id") == partner:
			await _send_action(candidate)
			return
	status.text = model.ui("turn.partner_not_allowed", {"name": model.name_of(partner)})


func _choose_ref_action(ref: String) -> void:
	var candidates = model.ref_actions(ref)
	if candidates.size() == 1:
		if int(model.held_action().get("index", -1)) != int(candidates[0].index):
			_choose_action(candidates[0], model.signature())
	elif candidates.size() > 1:
		tab = "choices"
		_render_choices(candidates)


func _set_tab(value: String) -> void:
	_hide_preview()
	tab = "choices" if value == "market" else value
	_render_choices()


func _reset_board() -> void:
	board.reset_view()


func _action_button(action: Dictionary, description = "", zone = "") -> void:
	var ref = ""
	if Model.DECK_TOP_CHOICES.has(action.action_id):
		ref = model.top_choice_card()
	for value in action.get("arguments", {}).values():
		if value is String and not model.entry(value).is_empty():
			ref = value
			break
	var row = HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	content.add_child(row)
	var apply = _apply_placement if action.action_id == "agent_turn" else _choose_action
	var button = ActionChoice.new()
	row.add_child(button)
	button.setup(self, action, description, zone, ref, apply.bind(action, model.signature()))
	if not ref.is_empty():
		_bind_preview(button, ref)
	if not model.preview_refs(action).is_empty() or not ref.is_empty() or action.get("subcommittee_preview") is Dictionary:
		var details = _button(row, "ⓘ", _action_details.bind(action, ref))
		details.custom_minimum_size = Vector2(28, 28)
		details.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		_compact_button(details)
		details.tooltip_text = model.ui("render.effect_preview_title")
		details.set_meta("action_detail_index", int(action.index))


func _action_details(action: Dictionary, ref: String) -> void:
	if not model.offered(action):
		return
	var parts = tools_ui._dialog(model.ui("render.effect_preview_title"), Vector2i(920, 600))
	parts[0].set_meta("action_detail_index", int(action.index))
	var zone = str(model.choice_zones(model.actions()).get(int(action.index), ""))
	_label(parts[1], model.live_description(action) + model.choice_suffix(zone), 18).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var refs = model.preview_refs(action)
	if not ref.is_empty() and ref not in refs:
		refs.push_front(ref)
	for target in refs:
		var entry = model.entry(target)
		if entry.get("options") is Array:
			var option_index = int(action.arguments.get("cost_option", 0))
			if option_index >= 0 and option_index < entry.options.size():
				entry = entry.duplicate(true)
				entry.options = [entry.options[option_index]]
		elif action.action_id == "play_intrigue" and action.arguments.get("option") != null:
			var lines = model.localized(entry, "text")
			var option_index = int(action.arguments.option)
			if lines is Array and option_index >= 0 and option_index < lines.size():
				entry = entry.duplicate(true)
				entry.text = [lines[option_index]]
				entry.erase("text_ko")
		var detail = _entry_panel(parts[1], target, entry)
		detail.heading.set_meta("action_preview_ref", target)
	var preview = action.get("subcommittee_preview")
	if preview is Dictionary:
		for line in preview.get("lines", []):
			_label(parts[1], model.phrase(model.localized(line, "text")) + ("\n" + model.phrase(model.localized(line, "reason")) if not line.get("enabled", false) else ""), 16).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _render_choices(filtered: Array = []) -> void:
	_clear(content)
	finish_button.disabled = true
	finish_button.text = model.finish_text()
	selection.text = model.native("카드와 칸을 선택해 에이전트를 보내세요") if not model.placements().is_empty() else model.prompt() if not model.prompt().is_empty() else model.native("다른 플레이어의 차례입니다")
	if not model.selected_card.is_empty():
		selection.text = model.name_of(model.selected_card) + (" + " + model.name_of(model.selected_partner) if not model.selected_partner.is_empty() else "") + "  →  " + (model.name_of(model.selected_space) if not model.selected_space.is_empty() else model.native("칸을 선택하세요"))
	elif not model.selected_space.is_empty():
		selection.text = model.name_of(model.selected_space) + "  →  " + model.native("카드를 선택하세요")
	var held = model.held_action()
	if not held.is_empty():
		finish_button.disabled = busy
	elif model.summary().get("confirmation") == model.active_seat:
		finish_button.disabled = busy
	else:
		finish_button.disabled = busy or model.finish_action().is_empty()
	if tab == "log":
		_render_log()
		return
	if tab == "table":
		_render_table()
		return
	if model.summary().get("finished", false) and tools_ui.review.is_empty():
		_render_results()
		return
	if not tools_ui.review.is_empty():
		tools_ui.render_review(content)
		return
	expansions.decision_header(content)
	if model.summary().get("confirmation") == model.active_seat:
		_label(content, model.native("선택을 바꾸려면 되돌리기를, 마치려면 턴 종료를 누르세요."), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if not filtered.is_empty():
		for action in filtered:
			_action_button(action)
		return
	if not model.placements().is_empty():
		var full_list = tools_ui.prefs.get("full_action_list", false)
		var list_toggle = _button(content, model.ui("turn.show_steps") if full_list else model.ui("turn.show_full_list", {"count": model.placements().size()}), func():
			tools_ui.prefs.full_action_list = not full_list
			tools_ui.save_preferences()
			model.clear_pick()
			_render()
		)
		list_toggle.set_meta("action_list_toggle", true)
		list_toggle.custom_minimum_size.y = 30
		list_toggle.add_theme_font_size_override("font_size", 12)
		list_toggle.flat = true
		var picked = HFlowContainer.new()
		content.add_child(picked)
		for part in ["card", "partner", "space"]:
			var ref = model.get("selected_" + part)
			if not str(ref).is_empty():
				var chip = _button(picked, model.name_of(ref) + " ×", func():
					model.clear_pick(part)
					_render()
				)
				chip.custom_minimum_size = Vector2(minf(230, maxf(90, chip.get_minimum_size().x)), 34)
				chip.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
				chip.set_meta("clear_pick", part)
		if full_list:
			for action in model.placements():
				_action_button(action)
		elif not model.selected_card.is_empty() and not model.selected_space.is_empty():
			for action in model.picked_placements():
				_action_button(action)
		elif not model.selected_card.is_empty():
			var spaces: Dictionary = {}
			for action in model.picked_placements():
				spaces[action.arguments.space_id] = true
			for space in spaces:
				var button = _button(content, model.name_of(space), _choose_ref.bind(space))
				_bind_preview(button, space)
		elif not model.selected_space.is_empty():
			var cards: Dictionary = {}
			for action in model.placements("", model.selected_space):
				cards[action.arguments.card_id] = true
			for card in cards:
				_button(content, model.name_of(card), _choose_ref.bind(card))
		else:
			_label(content, model.native("손패의 카드를 고르면 보드에서 갈 수 있는 칸이 빛납니다."), 15).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	choices.render(model.actions().filter(func(action): return action.action_id != "agent_turn" and (action.action_id not in Model.END_ACTIONS or action.action_id == "scouts_call")))


func _render_market() -> void:
	_clear(market_content)
	var heading = HBoxContainer.new()
	heading.add_theme_constant_override("separation", 4)
	market_content.add_child(heading)
	_label(heading, model.native("공용 카드"), 14).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var expand = _button(heading, model.native("크게"), func(): _open_pile(model.native("임페리움 열 · 살펴보기"), model.view().get("imperium_row", [])))
	expand.custom_minimum_size.y = 26
	expand.add_theme_font_size_override("font_size", 12)
	_compact_button(expand)
	expand.set_meta("market_expand", true)
	var decision = model.summary().get("decision")
	if decision is Dictionary and decision.get("persuasion") != null:
		_label(market_content, model.native("설득력 %d 남음") % int(decision.persuasion), 14)
	_label(market_content, model.native("임페리움 열"), 13)
	var refs = model.view().get("imperium_row", [])
	var width = maxi(68, floori((market_scroll.custom_minimum_size.x - 12) / 2))
	for index in range(0, refs.size(), 2):
		var row = HBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		market_content.add_child(row)
		for offset in range(mini(2, refs.size() - index)):
			_card(row, refs[index + offset], width, int(width * 1.42) + 42).set_meta("table_card", "market")
	_label(market_content, model.native("예비 더미"), 13)
	for reserve in model.view().get("reserve_stacks", []):
		var row = HBoxContainer.new()
		row.add_theme_constant_override("separation", 5)
		market_content.add_child(row)
		var ref = str(reserve[0])
		_card(row, ref, width, int(width * 1.42) + 42).set_meta("table_card", "market")
		var text = VBoxContainer.new()
		text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(text)
		_label(text, model.native("%d장") % int(reserve[1]), 12)
	_label(market_content, model.native("마우스를 올려 크게 보기"), 11)


func _render_results() -> void:
	_label(content, model.native("게임 종료 · 최종 순위"), 22)
	for standing in model.summary().get("standings", []):
		var seat = int(standing.player)
		var body = VBoxContainer.new()
		var panel = _panel(content)
		panel.add_child(body)
		_label(body, model.native("%d위 · %s · %d점") % [int(standing.rank), model.seat_name(seat), int(standing.victory_points)], 20)
		_label(body, model.native("스파이스 %d · 솔라리 %d · 물 %d\n수비대 %d") % [int(standing.spice), int(standing.solari), int(standing.water), int(standing.troops_garrison)], 14)
	_label(content, model.native("테이블 상세에서 각자의 카드와 이번 판을 다시 살펴볼 수 있습니다."), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _render_table() -> void:
	_label(content, model.native("현재 교전"), 20)
	for ref in model.view().get("current_conflict_ids", []):
		_button(content, model.name_of(ref) + model.native(" · 보상 보기"), _open_details.bind(ref))
	expansions.current_conflicts(content)
	_label(content, model.native("방어벽: ") + (model.native("있음") if model.view().get("shield_wall_present", true) else model.native("파괴됨")), 14)
	for player in model.view().get("players", []):
		var who = model.seat_name(int(player.player))
		var leader_name = model.name_of(str(player.leader_id)) if player.leader_id != null else model.native("지도자 선택 대기")
		_label(content, who + " · " + leader_name, 19)
		if player.leader_id != null:
			_button(content, model.native("지도자 능력 보기"), _open_details.bind(str(player.leader_id)))
		var tracks: PackedStringArray = []
		for faction in player.get("influence", {}):
			tracks.append("%s %d" % [model.name_of(faction), int(player.influence[faction])])
		_label(content, " / ".join(tracks), 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		for flags in [["alliance_faction_ids", model.native("동맹")], ["control_space_ids", model.native("지배")]]:
			var names: PackedStringArray = []
			for ref in player.get(flags[0], []):
				names.append(model.name_of(str(ref)))
			_label(content, flags[1] + ": " + (" / ".join(names) if not names.is_empty() else model.native("없음")), 14)
		expansions.player_details(content, player)
		_label(content, model.native("스파이: 보급 %d · 보드 %d · 배치 대기 %d\n병력: 보급 %d · 수비대 %d · 교전 %d\n모래벌레 %d · 전투력 %d") % [int(player.spies_supply), player.spy_post_ids.size(), int(player.get("track_spies_owed", 0)), int(player.troops_supply), int(player.troops_garrison), int(player.troops_conflict), int(player.sandworms_conflict), int(player.combat_strength)], 14)
		for group in [["in_play", model.native("플레이한 카드")], ["discard_pile", model.native("버린 카드")], ["trashed", model.native("폐기한 카드")], ["intrigue_faceup", model.native("공개된 책략")], ["objective_ids", model.native("목표")], ["won_conflict_ids", model.native("승리한 교전")], ["face_down_battle_card_ids", model.native("뒤집힌 전투 카드")]]:
			var refs = player.get(group[0], [])
			_button(content, model.native("%s · %d장") % [group[1], refs.size()], _open_pile.bind(who + " · " + group[1], refs))
		if int(player.player) == model.active_seat:
			var deck = model.view().get("private", {}).get("deck_cards", [])
			_button(content, model.native("내 덱 구성 · %d장") % deck.size(), _open_pile.bind(model.native("내 덱 구성 · 순서 비공개"), deck, false, ["private", "deck_cards"]))
		else:
			_label(content, model.native("손패 %d장 · 덱 %d장") % [int(player.hand_size), int(player.deck_size)], 14)
	_button(content, model.native("책략 버린 더미"), _open_pile.bind(model.native("책략 버린 더미"), model.view().get("intrigue_discard", [])))


func _open_pile(title: String, refs: Array, order = false, source_path: Array = []) -> AcceptDialog:
	_hide_preview()
	return preload("res://pile_viewer.gd").new().open(self, title, refs, order, source_path)


func _attach_dialog(dialog: Window) -> void:
	_hide_preview()
	# A popup opened from another popup belongs to that exclusive window.
	var parent: Node = self
	for child in find_children("*", "Window", true, false):
		if child.visible and child.exclusive and not child.is_queued_for_deletion():
			parent = child
	parent.add_child(dialog)


func _render_log(parent: VBoxContainer = null) -> void:
	log_ui.render(content if parent == null else parent)


func _inspect(ref: String) -> void:
	inspect_ref = ref
	_update_inspector()


func _entry_words(entry: Dictionary, ref: String = "") -> String:
	var parts: PackedStringArray = []
	var cost = entry.get("cost")
	if cost != null and not cost is Dictionary:
		parts.append((model.native("스파이스 비용 %d") if model.catalog.get("tech", {}).has(ref) else model.native("설득 비용 %d")) % int(cost))
	if entry.get("specimens") != null:
		parts.append(model.native("표본 비용 %d") % int(entry.specimens))
	if entry.get("currency") != null:
		parts.append(model.ui("panels.scouts_currency") + " " + model.phrase("{" + str(entry.currency) + "}"))
	for key in ["condition", "reward"]:
		if model.localized(entry, key) != null:
			parts.append(model.phrase(model.localized(entry, key)))
	for line in model.localized(entry, "lines") if model.localized(entry, "lines") is Array else []:
		parts.append(model.phrase(line))
	var icons = entry.get("agent_icons", [])
	if not icons.is_empty():
		var names: PackedStringArray = []
		for icon in icons:
			names.append(model.phrase("{spy}") if icon == "spy" else model.label("AGENT_ICON_GROUPS", icon))
		parts.append(model.native("에이전트: ") + " / ".join(names))
	if int(entry.get("persuasion", 0)) or int(entry.get("swords", 0)):
		parts.append(model.native("공개: 설득력 %d · 검 %d") % [int(entry.get("persuasion", 0)), int(entry.get("swords", 0))])
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
			parts.append(model.native("%d위: %s") % [index + 1, model.phrase(rewards[index])])
	if entry.get("icon") != null:
		parts.append(model.native("전투 아이콘: ") + model.name_of(str(entry.icon)))
	var notes = model.localized(entry, "notes")
	if notes is Array:
		for line in notes:
			parts.append(model.phrase(line))
	return "\n\n".join(parts)


func _update_inspector() -> void:
	if inspect_ref.is_empty():
		inspector_title.text = ""
		inspector_words.text = ""
		inspector_image.set_meta("image_path", "")
		inspector_image.texture = null
		return
	var entry = model.entry(inspect_ref)
	inspector_image.ref = inspect_ref
	inspector_title.text = model.name_of(inspect_ref)
	inspector_words.text = _entry_words(entry, inspect_ref)
	var path = _image_path(entry)
	inspector_image.visible = not path.is_empty()
	inspector_image.set_meta("image_path", path)
	inspector_image.texture = api.texture(path)


func _entry_panel(parent: Node, ref: String, entry: Dictionary, compact = false) -> Control:
	var panel = _panel(parent, 12)
	var detail = DetailEntry.new()
	panel.add_child(detail)
	detail.setup(self, ref, entry, compact)
	return detail


func _open_details(ref: String) -> void:
	var parts = tools_ui._dialog(model.name_of(ref), Vector2i(920, 600))
	parts[0].set_meta("detail_ref", ref)
	_entry_panel(parts[1], ref, model.entry(ref))
	expansions.leader_detail(parts[1], ref)


func _choose_action(action: Dictionary, expected: String) -> void:
	_hide_preview()
	if not tools_ui.review.is_empty() or model.active_seat not in model.owned_seats:
		return
	if busy or expected != model.signature() or not model.offered(action):
		return
	if action.get("sent_by_turn_end", false):
		if int(model.held_action().get("index", -1)) == int(action.index):
			model.held.clear()
		else:
			model.hold(action)
		_render()
		return
	await _send_action(action)


func _send_action(action: Dictionary) -> bool:
	if busy or not tools_ui.review.is_empty() or model.active_seat not in model.owned_seats or not model.offered(action):
		return false
	busy = true
	generation += 1
	var receipt = feedback.capture()
	_lock_controls()
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/actions", model.request_body(action))
	var accepted = _accept(reply)
	tab = "choices"
	await _sync()
	busy = false
	feedback.complete(receipt, action, reply)
	_render()
	return accepted


func _finish() -> void:
	if busy:
		return
	var bid = model.selected_quantity(model.actions().filter(func(action): return action.action_id == "scouts_bid"))
	if not bid.is_empty() and not model.finish_action().is_empty() and model.finish_action().action_id == "confirm_scouts_bid":
		var game = game_id
		var seat = model.active_seat
		var count = int(bid.arguments.count)
		if count != max(0, int(model.view().get("private", {}).get("scouts_bid", 0))):
			if not await _send_action(bid):
				return
		if game != game_id or seat != model.active_seat or max(0, int(model.view().get("private", {}).get("scouts_bid", -1))) != count:
			return
		for confirm in model.actions():
			if confirm.action_id == "confirm_scouts_bid":
				await _send_action(confirm)
				return
		return
	var held = model.held_action()
	if not held.is_empty():
		await _send_action(held)
	elif model.summary().get("confirmation") == model.active_seat:
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
	var data = {"seat": model.active_seat, "revision": int(model.summary().revision), "undo_count": int(model.summary().undo_count)}
	data.merge(extra)
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/" + path, data)
	var accepted = _accept(reply)
	await _sync()
	busy = false
	_render()
	return accepted


func _undo() -> void:
	await _mutate("undo", {"steps": 1})


func _save_now() -> void:
	var reply = await _save_game()
	if reply.get("ok", false):
		status.text = model.native("현재 판을 저장했습니다. 이어하기에서 다시 열 수 있습니다.")


func _save() -> void:
	tools_ui.save_dialog()


func _save_game(name: Variant = null) -> Dictionary:
	if game_id.is_empty() or busy:
		return {"ok": false}
	busy = true
	_lock_controls()
	var reply = await api.call_json(HTTPClient.METHOD_POST, "/games/" + game_id + "/save", {"name": name})
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
	dialog.title = model.native("저장한 게임 이어하기")
	dialog.ok_button_text = model.native("닫기")
	dialog.theme = theme
	dialog.set_meta("game_dialog", game_id)
	var root = VBoxContainer.new()
	root.custom_minimum_size = Vector2(600, 440)
	dialog.add_child(root)
	var body = _scroll(root)
	_label(body, model.native("저장된 판의 좌석과 규칙 옵션을 그대로 복원합니다."), 15).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var count = 0
	for saved in reply.data:
		if not model.supported_save(saved):
			continue
		count += 1
		var title = model.native("자동 저장") if saved.get("autosave", false) else str(saved.get("name", model.native("저장한 게임")))
		var row = HBoxContainer.new()
		body.add_child(row)
		var button = _button(row, model.native("%s · %d 라운드 · %s\n%s") % [title, int(saved.get("round_number", 0)), model.native("종료") if saved.get("finished", false) else model.label("PHASE_LABELS", str(saved.get("phase", ""))), str(saved.get("saved_at", ""))], func():
			dialog.hide()
			_load_game(str(saved.save_id))
			dialog.queue_free()
		)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.set_meta("save_id", str(saved.save_id))
		tools_ui.save_delete_button(row, str(saved.save_id), dialog)
	if count == 0:
		_label(body, model.native("이 시제품에서 이어할 저장이 없습니다."), 18)
	_attach_dialog(dialog)
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
	status.text = model.native("저장한 판을 복원하고 있습니다…")
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
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var focus = get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit or focus is OptionButton or event.ctrl_pressed or event.alt_pressed or event.meta_pressed:
		return
	# Embedded information/settings windows own their keyboard interaction.
	for window in find_children("*", "Window", true, false):
		if window.visible and not window.mouse_passthrough and not window.is_queued_for_deletion():
			return
	if game_id.is_empty():
		return
	match event.physical_keycode:
		KEY_C: tools_ui.toggle_market()
		KEY_S: tools_ui.toggle_seats()
		KEY_A: expansions.toggle_scouts()
		KEY_SLASH:
			if event.shift_pressed:
				tools_ui.help()
		KEY_ESCAPE:
			model.clear_pick()
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
	doorbell.stop()
	tools_ui.playback = false
	effects.shutdown()
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
	await _choose_ref(first.arguments.card_id)
	await _choose_ref(first.arguments.space_id)
	if int(model.summary().revision) == 0:
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
		var has_end = model.summary().get("confirmation") == model.active_seat
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
	# The server may wait up to eight seconds for a single AI presentation
	# cue. Three seats need a bounded time window, not fifty fast polls.
	var hand_back_deadline = Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < hand_back_deadline:
		await get_tree().create_timer(0.1).timeout
		await _sync()
		var decision = model.summary().get("decision")
		if decision is Dictionary and int(decision.get("owner", -1)) == model.active_seat and model.summary().get("thinking") == null:
			print("GODOT_SMOKE_OK ", JSON.stringify({"revision": model.summary().revision, "undo_count": model.summary().undo_count, "legal_actions": model.actions().size()}))
			smoke_done = true
			await _quit_cleanly()
			return
	_smoke_fail("AI did not hand back the turn")


func _wait_images() -> void:
	for attempt in range(100):
		if api.image_workers == 0:
			break
		await get_tree().create_timer(0.1).timeout
	await get_tree().process_frame
	await get_tree().process_frame


func _ref_button(root: Node, ref: String) -> Button:
	if ref.is_empty():
		return null
	for child in root.get_children():
		if child is Button and child.get_meta("instance_ref", "") == ref:
			return child
		var found = _ref_button(child, ref)
		if found != null:
			return found
	return null


func _move_pointer(point: Vector2) -> void:
	var event = InputEventMouseMotion.new()
	event.position = get_viewport().get_final_transform() * point
	event.global_position = event.position
	Input.parse_input_event(event)
	await get_tree().process_frame
	await get_tree().create_timer(0.35).timeout


func _check_layout() -> bool:
	var window_rect = Rect2(Vector2.ZERO, size)
	for button in content.find_children("*", "Button", true, false):
		if button.has_meta("action_reading") and not button.layout_fits():
			_smoke_fail("choice title, costs or hints leave their button")
			return false
	for entry_view in find_children("*", "BoxContainer", true, false):
		if entry_view.has_meta("entry_view") and entry_view.is_visible_in_tree() and entry_view.get_window().visible and not entry_view.layout_fits():
			_smoke_fail("detail artwork and text overlap or leave their entry")
			return false
	if hand_scroll.visible != (hand.get_child_count() > 0):
		_smoke_fail("empty hand reserves card space or a populated hand is hidden")
		return false
	for panel in seats.get_children():
		for item in panel.find_children("*", "Control", true, false):
			if ["vp_seat", "seat_name", "seat_turn", "seat_view", "seat_clock", "resource_amount"].any(func(key): return item.has_meta(key)) and not panel.get_global_rect().grow(1).encloses(item.get_global_rect()):
				_smoke_fail("player name, state, clock, resources or victory points leave their panel")
				return false
	for row in find_children("*", "Button", true, false):
		if row.has_meta("history_row") and row.is_visible_in_tree() and not row.layout_fits():
			_smoke_fail("history actor or action text leaves its row")
			return false
	for control in [board, market_scroll, content.get_parent(), finish_button, hand_panel]:
		if not window_rect.encloses(control.get_global_rect()):
			print("GODOT_LAYOUT_DIAGNOSTIC ", JSON.stringify({"control": str(control.name), "parent": str(control.get_parent().name), "rect": str(control.get_global_rect()), "viewport": str(size)}))
			_smoke_fail("table control outside the window")
			return false
	if board.size.x < 300 or board.map_rect.size.x < 300:
		_smoke_fail("board lost its reading area")
		return false
	if finish_button.get_global_rect().position.y < content.get_parent().get_global_rect().end.y:
		_smoke_fail("turn end overlaps choices")
		return false
	for group in [hand, market_content]:
		for card in group.find_children("*", "Button", true, false):
			if card.has_meta("market_expand"):
				var rect = card.get_global_rect()
				var pane = market_scroll.get_global_rect()
				if rect.position.x < pane.position.x or rect.end.x > pane.end.x:
					_smoke_fail("shared-market expand button clipped horizontally")
					return false
			if not card.has_meta("instance_ref"):
				continue
			var bounds = Rect2(Vector2.ZERO, card.size)
			if card.caption == null or card.caption.text != model.name_of(card.ref) or not bounds.encloses(card.caption.get_rect()) or not bounds.encloses(card.face.get_rect()) or card.face.get_rect().intersects(card.caption.get_rect()):
				_smoke_fail("card name/face missing, overlapping or outside its control")
				return false
			var badges: Array[Rect2] = []
			for child in card.get_children():
				if child.has_meta("card_state") or child.has_meta("card_cost"):
					var rect = child.get_rect()
					if not bounds.encloses(rect) or badges.any(func(previous): return previous.intersects(rect)):
						_smoke_fail("card state/cost badges overlap or escape the control")
						return false
					badges.append(rect)
	return true


func _check_hover(ref: String, source: Control) -> bool:
	await _move_pointer(source.get_global_rect().get_center())
	if not preview.visible or inspect_ref != ref or inspector_image.texture == null:
		print("GODOT_HOVER_DIAGNOSTIC ", JSON.stringify({"expected": ref, "actual": inspect_ref, "visible": preview.visible, "rect": str(source.get_global_rect()), "pointer": str(get_global_mouse_position()), "scale": get_window().content_scale_factor, "allowed": _pointer_allowed(), "dragging": get_viewport().gui_is_dragging(), "source": str(hover_source), "hint": pointer_hint.text, "modal": find_children("*", "Window", true, false).filter(func(window): return window.visible and not window.is_queued_for_deletion()).map(func(window): return window.title)}))
		_smoke_fail("native hover did not show the matching large card")
		return false
	if not Rect2(Vector2.ZERO, size).encloses(preview.get_global_rect()) or preview.get_global_rect().intersects(source.get_global_rect()):
		_smoke_fail("hover outside window or covering its control")
		return false
	if "spy" in model.entry(ref).get("agent_icons", []) and inspector_words.text.contains("에이전트: Spy"):
		_smoke_fail("untranslated spy icon in the card preview")
		return false
	if inspector_image.size.x < 250 or preview.mouse_filter != Control.MOUSE_FILTER_IGNORE:
		_smoke_fail("hover card too small or consumes input")
		return false
	return true


func _run_capture() -> void:
	# Native mouse movement must not overwrite injected test input on Windows.
	# Normal play keeps the default mouse handling.
	get_window().mouse_passthrough = true
	var watchdog = Timer.new()
	watchdog.wait_time = 180
	watchdog.one_shot = true
	watchdog.timeout.connect(func(): _smoke_fail("capture timeout"))
	add_child(watchdog)
	watchdog.start()
	tools_ui.prefs.sound = false
	if not await _create_game(11):
		_smoke_fail("capture create")
		return
	await _wait_images()
	if not _check_layout():
		return
	await _capture("table")
	# Missing artwork must still leave a named, readable, clickable hand card.
	var original_catalog = model.catalog
	model.catalog = model.catalog.duplicate(true)
	var fallback_ref = str(model.view().private.hand[0])
	var fallback_entry = model.entry(fallback_ref)
	fallback_entry.image = null
	fallback_entry.erase("image_ko")
	_render()
	await _wait_images()
	var fallback_card = _ref_button(hand, fallback_ref)
	if fallback_card == null or fallback_card.fallback == null or fallback_card.fallback.text.is_empty() or not _check_layout():
		_smoke_fail("missing-art hand card lost its text or input control")
		return
	await _capture("table-no-art")
	model.catalog = original_catalog
	_render()
	await _wait_images()
	var native_hand = model.view().private.hand.duplicate()
	var revision = model.summary().revision
	if native_hand.size() >= 2:
		await _drag(_ref_button(hand, native_hand[1]).get_global_rect().get_center(), _ref_button(hand, native_hand[0]).get_global_rect().get_center())
		if layout_ui.ordered(native_hand, "hand")[0] != native_hand[1] or model.view().private.hand != native_hand or model.summary().revision != revision:
			_smoke_fail("native hand drag changes only personal presentation")
			return
	var grip = seat_scroll.get_parent().get_child(seat_scroll.get_index() + 1)
	var initial_width = seat_scroll.size.x
	await _drag(grip.get_global_rect().get_center(), grip.get_global_rect().get_center() + Vector2(24, 0))
	if seat_scroll.size.x <= initial_width:
		_smoke_fail("native column drag")
		return
	layout_ui.reset()
	await _wait_images()
	var first = model.placements()[0]
	var card = _ref_button(hand, first.arguments.card_id)
	if card == null:
		_smoke_fail("visible card button")
		return
	if not await _check_hover(first.arguments.card_id, card):
		return
	await _capture("card-hover")
	await _click(card.get_global_rect().get_center())
	if model.selected_card != first.arguments.card_id:
		_smoke_fail("native card click with hover open")
		return
	await _wait_images()
	var selected_card = _ref_button(hand, first.arguments.card_id)
	var checked = false
	for child in selected_card.get_children():
		if child.has_meta("card_state") and child.text.begins_with("✓"):
			checked = true
	if not checked or not _check_layout():
		_smoke_fail("selected card lacks a non-color state marker")
		return
	await _capture("card-selected")
	var clear_card: Button
	for button in content.find_children("*", "Button", true, false):
		if button.get_meta("clear_pick", "") == "card":
			clear_card = button
	if clear_card == null or clear_card.size.x < 70:
		_smoke_fail("selected card's clear control lost its readable name")
		return
	await _click(clear_card.get_global_rect().get_center())
	if not model.selected_card.is_empty() or model.summary().revision != revision:
		_smoke_fail("clear pick must only clear the local selection")
		return
	await _wait_images()
	await _click(_ref_button(hand, first.arguments.card_id).get_global_rect().get_center())
	var point = board._box(model.entry(first.arguments.space_id).box).get_center()
	await _click(board.get_global_transform() * point)
	while busy or refreshing:
		await get_tree().process_frame
	var auto_placed = int(model.summary().revision) > int(revision)
	if not auto_placed and model.selected_space != first.arguments.space_id:
		_smoke_fail("native board click")
		return
	await _wait_images()
	await _capture("selected")
	# Wheel zoom keeps the pointed-at board space under the cursor.
	var wheel = InputEventMouseButton.new()
	wheel.button_index = MOUSE_BUTTON_WHEEL_UP
	wheel.pressed = true
	wheel.position = get_viewport().get_final_transform() * (board.get_global_transform() * point)
	wheel.global_position = wheel.position
	Input.parse_input_event(wheel)
	await get_tree().process_frame
	await get_tree().process_frame
	if board.zoom <= 1.0 or board._hit(point) != first.arguments.space_id:
		_smoke_fail("wheel zoom moved the selected space away from the cursor")
		return
	await _capture("zoom")
	_reset_board()
	await _wait_images()
	var placement_button: Button
	# After a unique placement there is no placement chooser. Hover another
	# real card-bearing choice instead of requiring the old extra click.
	for button in content.find_children("*", "Button", true, false):
		if (not auto_placed and int(button.get_meta("action_index", -1)) == int(first.index)) or (auto_placed and button.has_meta("preview_ref")):
			placement_button = button
	if placement_button != null:
		var hover_ref = str(placement_button.get_meta("preview_ref", first.arguments.card_id))
		if not await _check_hover(hover_ref, placement_button):
			return
		if preview.get_global_rect().intersects(content.get_parent().get_global_rect()):
			_smoke_fail("action hover covers the decision column")
			return
		await _capture("choice-hover")
	_hide_preview()
	if auto_placed:
		if not await _mutate("undo", {"steps": 1}):
			_smoke_fail("native automatic placement undo")
			return
	_set_tab("table")
	await _capture("tableau")
	var pile = _open_pile(model.native("내 손패 · 살펴보기"), model.view().get("private", {}).get("hand", []))
	await _capture("pile")
	pile.confirmed.emit()
	await get_tree().process_frame
	_set_tab("choices")
	await _wait_images()
	# Reveal and buy through actual input, using only the server's choices.
	var reveal: Dictionary = {}
	for action in model.actions():
		if action.action_id == "reveal_turn":
			reveal = action
	if reveal.is_empty():
		_smoke_fail("reveal choice absent")
		return
	var before_reveal = model.signature()
	for button in content.find_children("*", "Button", true, false):
		if int(button.get_meta("action_index", -1)) == int(reveal.index):
			await _click(button.get_global_rect().get_center())
			break
	while busy or refreshing:
		await get_tree().process_frame
	if not model.held_action().is_empty():
		await _click(finish_button.get_global_rect().get_center())
		while busy or refreshing:
			await get_tree().process_frame
	if model.signature() == before_reveal:
		_smoke_fail("native reveal click did not advance")
		return
	await _wait_images()
	await _capture("market")
	# Exercise compact badges with English names while purchases are legal.
	get_window().size = Vector2i(1100, 740)
	model.language = "en"
	_render()
	await _wait_images()
	if not _check_layout():
		return
	await _capture("market-en-narrow")
	model.language = "ko"
	get_window().size = Vector2i(1440, 900)
	_render()
	await _wait_images()
	var purchase_ref = ""
	for action in model.actions():
		if str(action.action_id).begins_with("acquire_imperium"):
			for value in action.arguments.values():
				if value is String and value in model.view().get("imperium_row", []):
					purchase_ref = value
					break
		if not purchase_ref.is_empty():
			break
	var market_card = _ref_button(market_content, purchase_ref)
	if market_card == null or not await _check_hover(purchase_ref, market_card):
		_smoke_fail("market purchase control absent")
		return
	await _capture("market-hover")
	var before = model.signature()
	await _click(market_card.get_global_rect().get_center())
	while busy or refreshing:
		await get_tree().process_frame
	if model.signature() == before or purchase_ref in model.view().get("imperium_row", []):
		_smoke_fail("native market click did not purchase")
		return
	await _wait_images()
	for line in log_content.get_children():
		var ref = str(line.get_meta("preview_ref", ""))
		if not ref.is_empty():
			if not await _check_hover(ref, line):
				return
			await _capture("log-hover")
			_hide_preview()
			break
	get_window().size = Vector2i(1100, 740)
	await _wait_images()
	if not _check_layout():
		return
	await _capture("narrow")
	var row_refs = model.view().get("imperium_row", [])
	if not row_refs.is_empty():
		var narrow_card = _ref_button(market_content, row_refs[0])
		if not await _check_hover(row_refs[0], narrow_card):
			return
		await _capture("narrow-hover")
	_hide_preview()
	get_window().size = Vector2i(1440, 900)
	await _wait_images()
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
		if child.get_meta("game_option", "") == "leader_draft":
			draft = child
	if draft == null:
		_smoke_fail("draft setting absent")
		return
	if draft.button_pressed:
		await _click(Vector2(draft_dialog.position) + draft.get_global_rect().get_center())
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
	if inspector_image.texture != null or not inspector_title.text.is_empty() or preview.visible:
		_smoke_fail("new game kept another game's inspector")
		return
	await _capture("draft")
	model.language = "en"
	_render()
	await _wait_images()
	if new_button.text != "New Game" or not _check_layout():
		_smoke_fail("English native chrome or layout")
		return
	await _capture("table-en")
	if not await _capture_scaled_tables():
		return
	model.language = "ko"
	_render()
	print("GODOT_CAPTURE_OK")
	await _quit_cleanly()


func _capture_scaled_tables() -> bool:
	# Exercise native rendering and input at FHD, QHD and 4K without changing
	# the user's desktop resolution or relying on the test monitor's DPI.
	display_ui.set_process(false)
	if not await _create_game(11):
		_smoke_fail("scaled gameplay create")
		return false
	for pixels in [Vector2i(1920, 1080), Vector2i(2560, 1440), Vector2i(3840, 2160)]:
		display_ui.monitor_scale = display_ui.preferred_scale(pixels)
		get_window().size = pixels
		display_ui._apply_scale()
		await _wait_images()
		if not is_equal_approx(get_window().content_scale_factor, display_ui.monitor_scale):
			_smoke_fail("native resolution did not acquire its automatic UI scale")
			return false
		for language in ["ko", "en"]:
			model.language = language
			_render()
			await _wait_images()
			if not _check_layout():
				return false
			var name = "scaled-%dx%d-%s" % [pixels.x, pixels.y, language]
			await _capture(name)
			var ref = str(model.view().get("imperium_row", [])[0])
			var card = _ref_button(market_content, ref)
			if card == null or not await _check_hover(ref, card):
				return false
			await _capture(name + "-hover")
			_hide_preview()
			await _click(new_button.get_global_rect().get_center())
			var dialog: Window
			for child in get_children():
				if child is ConfirmationDialog and child.visible:
					dialog = child
			if dialog == null:
				_smoke_fail("scaled click did not open the new-game dialog")
				return false
			await get_tree().process_frame
			if not Rect2(Vector2.ZERO, size).encloses(Rect2(Vector2(dialog.position), Vector2(dialog.size))):
				_smoke_fail("scaled popup outside the logical viewport")
				return false
			await _capture(name + "-dialog")
			dialog.queue_free()
			await get_tree().process_frame
			var pile = _open_pile("Cards", model.view().get("imperium_row", []))
			await get_tree().process_frame
			await get_tree().process_frame
			pile.position = Vector2i(size) - pile.size + Vector2i(80, 80)
			_fit_columns()
			await get_tree().process_frame
			if not Rect2(Vector2.ZERO, size).encloses(Rect2(Vector2(pile.position), Vector2(pile.size))):
				_smoke_fail("scaled information popup was clamped against physical pixels")
				return false
			await _capture(name + "-pile")
			pile.queue_free()
			await get_tree().process_frame
	return true


func _drag(start: Vector2, end: Vector2) -> void:
	start = get_viewport().get_final_transform() * start
	end = get_viewport().get_final_transform() * end
	var press = InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = start
	press.global_position = start
	Input.parse_input_event(press)
	await get_tree().process_frame
	var previous = start
	for step in range(1, 9):
		var motion = InputEventMouseMotion.new()
		motion.position = start.lerp(end, float(step) / 8)
		motion.global_position = motion.position
		motion.relative = motion.position - previous
		motion.button_mask = MOUSE_BUTTON_MASK_LEFT
		Input.parse_input_event(motion)
		previous = motion.position
		await get_tree().process_frame
	press = InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = false
	press.position = end
	press.global_position = end
	Input.parse_input_event(press)
	await get_tree().process_frame
	await get_tree().process_frame


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
	if not _check_layout():
		return
	if name == "selected":
		var pane = content.get_parent().get_global_rect()
		var visible_actions = 0
		for node in content.find_children("*", "Button", true, false):
			if pane.intersects(node.get_global_rect()):
				visible_actions += 1
		if visible_actions == 0 or finish_button.get_global_rect().position.y < pane.end.y:
			_smoke_fail("selected action visibility or overlap")
			return
	var image = get_viewport().get_texture().get_image()
	var error = image.save_png(capture_dir.path_join(name + ".png"))
	if error != OK:
		_smoke_fail("save capture")
