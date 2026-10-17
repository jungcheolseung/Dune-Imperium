extends Control

# The title screen owns navigation, not game rules or seat authorization.
# Server commands go only to the launcher's private local mailbox.
var table: Control
var control_dir = ""
var page = "home"
var language = ""
var request_id = 0
var waiting = false
var owned: Dictionary = {}
var discovery: Array = []
var suggested_ip = ""
var fields: Dictionary = {}
var body: VBoxContainer
var message: Label
var host_status: Label
var address_select: OptionButton
var port: SpinBox
var invite: LineEdit
var copy_button: Button
var start_button: Button
var stop_button: Button
var room_button: Button
var single_resume: Button


func setup(owner_table: Control, directory: String) -> void:
	table = owner_table
	control_dir = directory
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	show_page("home")


static func parse_invite(value: String) -> Dictionary:
	var clean = value.strip_edges()
	var pattern = RegEx.new()
	pattern.compile("^https?://(\\[[0-9a-fA-F:]+\\]|[^/:@?#\\s]+)(:[0-9]{1,5})?/?#([^\\s]*)$")
	var found = pattern.search(clean)
	if found == null:
		return {}
	var number = found.get_string(2)
	if not number.is_empty() and (int(number.substr(1)) < 1 or int(number.substr(1)) > 65535):
		return {}
	var game = ""
	for pair in found.get_string(3).split("&"):
		if pair.get_slice("=", 0) == "admin":
			return {}
		if pair.get_slice("=", 0) == "game":
			if not game.is_empty():
				return {}
			game = pair.get_slice("=", 1).uri_decode()
	pattern.compile("^[A-Za-z0-9_-]+$")
	if pattern.search(game) == null:
		return {}
	return {"origin": clean.get_slice("#", 0).trim_suffix("/"), "game": game}


func _action(key: String, title: String, callback: Callable) -> Button:
	var button = table._button(body, table.model.native(title), callback)
	button.set_meta("front_action", key)
	button.custom_minimum_size.y = 52
	button.add_theme_font_size_override("font_size", 20)
	return button


func _row_action(row: HBoxContainer, key: String, title: String, callback: Callable) -> Button:
	var button = table._button(row, table.model.native(title), callback)
	button.set_meta("front_action", key)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return button


func _words(value: String, size = 15) -> Label:
	var label = table._label(body, table.model.native(value), size)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


func show_page(target: String) -> void:
	if waiting or table.busy:
		return
	page = target
	language = table.model.language
	visible = true
	table.table_surface.hide()
	table._hide_preview()
	table._clear(self)
	fields.clear()
	var background = ColorRect.new()
	background.color = Color("101719")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	var margin = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for edge in ["margin_left", "margin_right", "margin_top", "margin_bottom"]:
		margin.add_theme_constant_override(edge, 36)
	add_child(margin)
	var columns = HBoxContainer.new()
	columns.add_theme_constant_override("separation", 48)
	margin.add_child(columns)
	var identity = VBoxContainer.new()
	identity.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	identity.alignment = BoxContainer.ALIGNMENT_CENTER
	columns.add_child(identity)
	table._label(identity, "DUNE", 70).add_theme_color_override("font_color", Color("dbb576"))
	table._label(identity, table.model.native("임페리움: 봉기"), 30)
	var caption = table._label(identity, table.model.native("아라키스에서 펼쳐지는 권력의 게임"), 16)
	caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caption.add_theme_color_override("font_color", Color("a9aca4"))
	var panel = table._panel(columns, 24)
	panel.custom_minimum_size.x = 540
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body = table._scroll(panel)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.alignment = BoxContainer.ALIGNMENT_CENTER if page == "home" else BoxContainer.ALIGNMENT_BEGIN
	body.add_theme_constant_override("separation", 14)
	var titles = {"home": "메인 화면", "single": "싱글플레이", "multi": "멀티플레이", "host": "서버 열기", "join": "초대 링크로 참가"}
	_words(titles.get(page, "메인 화면"), 28).add_theme_color_override("font_color", Color("dbb576"))
	message = _words("")
	message.add_theme_color_override("font_color", Color("dfbb86"))
	match page:
		"home":
			_action("single", "싱글플레이", func(): show_page("single"))
			_action("multi", "멀티플레이", func(): show_page("multi"))
			_action("settings", "설정", table.tools_ui.settings)
			_action("quit", "게임종료", table._quit_cleanly)
			if not table.game_id.is_empty():
				_action("resume", "진행 중인 게임으로 돌아가기", show_table)
		"single":
			_words("혼자 AI 상대와 플레이합니다.")
			_action("new_single", "새 게임", func(): _single(false))
			_action("load_single", "이어하기", func(): _single(true))
			_action("back", "뒤로", func(): show_page("home"))
		"multi", "host":
			_host_tabs(true)
			_build_host()
		"join":
			_host_tabs(false)
			_words("친구가 보낸 방 초대 링크를 붙여 넣으세요.")
			var url = LineEdit.new()
			url.name = "invite_url"
			url.placeholder_text = "http://…/#game=…"
			url.custom_minimum_size.y = 44
			body.add_child(url)
			fields.invite_url = url
			_action("connect", "참가하기", func(): _join(url.text))
			url.text_submitted.connect(_join)
			_action("back", "뒤로", func(): show_page("multi"))
	for button in body.find_children("*", "Button", true, false):
		if not button.disabled:
			button.grab_focus()
			break


func refresh_language() -> void:
	if visible and language != table.model.language and not waiting:
		show_page(page)


func show_table() -> void:
	visible = false
	table.table_surface.show()


func _set_waiting(value: bool) -> void:
	waiting = value
	for button in find_children("*", "Button", true, false):
		if button.get_meta("front_action", "") == "quit":
			continue
		if value:
			button.set_meta("front_disabled", button.disabled)
			button.disabled = true
		elif button.has_meta("front_disabled"):
			button.disabled = button.get_meta("front_disabled")
			button.remove_meta("front_disabled")


func _request(operation: String, preferences: Dictionary = {}) -> Dictionary:
	if control_dir.is_empty():
		return {"ok": false, "message": table.model.native("서버를 관리하려면 게임 실행기로 시작해 주세요.")}
	if waiting:
		return {"ok": false, "message": table.model.native("서버 요청을 처리하고 있습니다.")}
	_set_waiting(true)
	request_id += 1
	var temporary = control_dir.path_join("request.tmp")
	var file = FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		_set_waiting(false)
		return {"ok": false, "message": table.model.native("서버 요청을 전달하지 못했습니다.")}
	file.store_string(JSON.stringify({"id": request_id, "operation": operation, "preferences": preferences}))
	file.close()
	var code = DirAccess.rename_absolute(temporary, control_dir.path_join("request.json"))
	if code != OK:
		_set_waiting(false)
		return {"ok": false, "message": table.model.native("서버 요청을 전달하지 못했습니다.")}
	var response_path = control_dir.path_join("response.json")
	var deadline = Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline and not table.closing:
		if FileAccess.file_exists(response_path):
			var result = JSON.parse_string(FileAccess.get_file_as_string(response_path))
			DirAccess.remove_absolute(response_path)
			if result is Dictionary and int(result.get("id", -1)) == request_id:
				_set_waiting(false)
				return result
		await get_tree().create_timer(0.05).timeout
	_set_waiting(false)
	return {"ok": false, "message": table.model.native("서버 응답을 기다리는 시간이 지났습니다. 다시 시도하세요.")}


func _confirm(title: String, callback: Callable) -> void:
	var dialog = ConfirmationDialog.new()
	dialog.title = table.model.native(title)
	dialog.dialog_text = table.model.native("이 앱이 연 서버를 끄면 참가자들의 연결도 끊깁니다. 현재 턴을 마치고 저장한 뒤 진행하세요.")
	dialog.ok_button_text = table.model.native("계속")
	dialog.cancel_button_text = table.model.native("취소")
	dialog.theme = table.theme
	add_child(dialog)
	dialog.confirmed.connect(func(): dialog.queue_free(); callback.call())
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered(Vector2i(560, 180))


func _single(load_saved: bool) -> void:
	if owned.get("running", false) and owned.get("mode") == "remote":
		_confirm("싱글플레이로 전환", func(): _open_single(load_saved))
	else:
		_open_single(load_saved)


func _open_single(load_saved: bool) -> void:
	message.text = table.model.native("게임을 준비하고 있습니다…")
	var host = table.tools_ui.prefs.get("host", {})
	var values = {"mode": "local", "checkpoint": host.get("checkpoint", ""), "python": host.get("python", "")}
	if not await _start(values):
		return
	if load_saved:
		table._show_saves()
	else:
		table.tools_ui.prefs.seats = ["human", "app_ai", "app_ai", "app_ai"]
		table.tools_ui.new_game()


func _start(values: Dictionary) -> bool:
	var result = await _request("start", {"host": values, "pace": table.tools_ui.prefs.get("pace", "fast")})
	if not result.get("ok", false):
		if result.has("running"):
			owned = result
			if page in ["host", "multi"]:
				_update_host_status()
		message.text = str(result.get("message", ""))
		return false
	var credentials = result.get("credentials", {})
	var key = str(credentials.get("key", ""))
	_set_waiting(true)
	var connected = await table.tools_ui.connect_server(str(result.origin), key, "", false)
	_set_waiting(false)
	credentials.clear()
	result.erase("credentials")
	owned = result
	if not connected:
		message.text = table.status.text
		return false
	message.text = ""
	return true


func _host_tabs(hosting: bool) -> void:
	var tabs = HBoxContainer.new()
	body.add_child(tabs)
	_row_action(tabs, "host", "서버 열기", func(): show_page("multi")).disabled = hosting
	_row_action(tabs, "join", "초대 링크로 참가", func(): show_page("join")).disabled = not hosting


func _build_host() -> void:
	body.add_theme_constant_override("separation", 8)
	_words("친구들과 같은 네트워크 또는 Tailscale로 연결할 수 있습니다.")
	host_status = _words("")
	var config = table.tools_ui.prefs.get("host", {})
	_words("연결 주소 · 포트", 14)
	var connection_row = HBoxContainer.new()
	body.add_child(connection_row)
	address_select = OptionButton.new()
	address_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	connection_row.add_child(address_select)
	address_select.item_selected.connect(func(index):
		var ip = str(address_select.get_item_metadata(index))
		if not ip.is_empty():
			fields.public_url.text = "http://" + ip + ":" + str(int(port.value))
	)
	port = SpinBox.new()
	port.min_value = 1
	port.max_value = 65535
	port.value = int(config.get("port", 8000))
	port.custom_minimum_size.x = 110
	connection_row.add_child(port)
	_words("친구에게 보낼 서버 주소", 14)
	var public_url = LineEdit.new()
	public_url.text = str(config.get("public_url", ""))
	public_url.placeholder_text = "http://192.168.1.10:8000"
	body.add_child(public_url)
	fields.public_url = public_url
	public_url.text_changed.connect(func(value):
		if address_select.selected > 0 and value != "http://" + str(address_select.get_item_metadata(address_select.selected)) + ":" + str(int(port.value)):
			address_select.select(0)
	)
	port.value_changed.connect(func(value):
		if address_select.selected >= 0:
			var ip = str(address_select.get_item_metadata(address_select.selected))
			if not ip.is_empty():
				public_url.text = "http://" + ip + ":" + str(int(value))
	)
	var advanced = VBoxContainer.new()
	var advanced_toggle = CheckButton.new()
	advanced_toggle.text = table.model.native("고급 설정")
	body.add_child(advanced_toggle)
	body.add_child(advanced)
	advanced.visible = false
	advanced_toggle.toggled.connect(func(value): advanced.visible = value)
	for pair in [["bind", "서버가 받을 주소", "0.0.0.0"], ["checkpoint", "선택: 학습 체크포인트 파일", ""], ["python", "선택: 학습 런타임 실행 파일", ""]]:
		table._label(advanced, table.model.native(pair[1]), 14)
		var row = HBoxContainer.new()
		advanced.add_child(row)
		var input = LineEdit.new()
		input.text = str(config.get(pair[0], pair[2]))
		input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(input)
		fields[pair[0]] = input
		if pair[0] in ["checkpoint", "python"]:
			table._button(row, table.model.native("파일 선택"), func():
				var file = FileDialog.new()
				file.access = FileDialog.ACCESS_FILESYSTEM
				file.file_mode = FileDialog.FILE_MODE_OPEN_FILE
				file.use_native_dialog = true
				add_child(file)
				file.file_selected.connect(func(path): input.text = path; file.queue_free())
				file.canceled.connect(file.queue_free)
				file.popup_centered(Vector2i(850, 600))
			)
	var server_row = HBoxContainer.new()
	body.add_child(server_row)
	start_button = _row_action(server_row, "start_server", "서버 켜기", _host)
	stop_button = _row_action(server_row, "stop_server", "서버 끄기", func(): _confirm("서버 끄기", _stop_host))
	_words("친구에게 보낼 초대 링크", 14)
	var invite_row = HBoxContainer.new()
	body.add_child(invite_row)
	invite = LineEdit.new()
	invite.name = "invite_link"
	invite.editable = false
	invite.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	invite.placeholder_text = table.model.native("방을 만든 뒤 초대 링크가 표시됩니다.")
	invite_row.add_child(invite)
	copy_button = _row_action(invite_row, "copy_invite", "초대 링크 복사", func(): DisplayServer.clipboard_set(invite.text); message.text = table.model.native("초대 링크를 복사했습니다."))
	copy_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	var rooms = HBoxContainer.new()
	body.add_child(rooms)
	room_button = _row_action(rooms, "new_room", "새 방 만들기", _new_room)
	_row_action(rooms, "load_room", "저장한 방 이어하기", func():
		if owned.get("mode") == "remote" and owned.get("running", false):
			table._show_saves()
	)
	if not table.game_id.is_empty():
		_action("resume", "진행 중인 게임으로 돌아가기", show_table)
	var footer = HBoxContainer.new()
	body.add_child(footer)
	_row_action(footer, "back", "뒤로", func(): show_page("home"))
	_row_action(footer, "refresh_addresses", "주소 새로고침", _inspect_host)
	_update_addresses()
	_update_host_status()
	if discovery.is_empty():
		_inspect_host()


func _update_addresses() -> void:
	address_select.clear()
	address_select.add_item(table.model.native("직접 입력"))
	address_select.set_item_metadata(0, "")
	var labels = {"tailscale": "Tailscale", "lan": "같은 네트워크", "outbound": "다른 네트워크 주소", "loopback": "이 PC에서만"}
	for candidate in discovery:
		if candidate.kind == "loopback":
			continue
		address_select.add_item(table.model.native(labels.get(candidate.kind, "연결 주소")) + " · " + str(candidate.ip))
		address_select.set_item_metadata(address_select.item_count - 1, candidate.ip)
	if fields.public_url.text.is_empty() and not suggested_ip.is_empty():
		fields.public_url.text = "http://" + suggested_ip + ":" + str(int(port.value))
	for index in range(1, address_select.item_count):
		if fields.public_url.text == "http://" + str(address_select.get_item_metadata(index)) + ":" + str(int(port.value)):
			address_select.select(index)
			break


func _update_host_status() -> void:
	var running = owned.get("running", false) and owned.get("mode") == "remote"
	host_status.text = table.model.native("● 서버 켜짐" if running else "■ 서버 꺼짐")
	start_button.text = table.model.native("서버 설정 적용" if running else "서버 켜기")
	stop_button.disabled = not running
	room_button.disabled = not running
	var can_invite = running and table.api.base_url == owned.get("origin") and not table.game_id.is_empty()
	invite.text = str(owned.get("room_base", "")).trim_suffix("/") + "/#game=" + table.game_id if can_invite else ""
	copy_button.disabled = not can_invite
	for button in body.find_children("*", "Button", true, false):
		if button.get_meta("front_action", "") == "load_room":
			button.disabled = not running


func _inspect_host() -> void:
	message.text = table.model.native("이 컴퓨터의 연결 주소를 확인하고 있습니다…")
	var result = await _request("inspect")
	if not result.get("ok", false):
		message.text = str(result.get("message", ""))
		return
	owned = result
	discovery = result.get("addresses", [])
	suggested_ip = str(result.get("suggested_ip", "")) if result.get("suggested_ip") != null else ""
	message.text = ""
	_update_addresses()
	_update_host_status()


func _host() -> void:
	if owned.get("running", false):
		_confirm("서버 설정 적용", _open_host)
	else:
		_open_host()


func _open_host() -> void:
	message.text = table.model.native("서버를 켜고 있습니다…")
	var values = {"mode": "remote", "port": int(port.value)}
	for key in ["bind", "public_url", "checkpoint", "python"]:
		values[key] = fields[key].text.strip_edges()
	if not await _start(values):
		return
	table.tools_ui.prefs.host = values
	table.tools_ui.save_preferences()
	_update_host_status()


func _stop_host() -> void:
	message.text = table.model.native("서버를 끄고 있습니다…")
	var result = await _request("stop")
	if not result.get("ok", false):
		message.text = str(result.get("message", ""))
		return
	owned = result
	table.tools_ui.leave_game()
	table.api.base_url = ""
	table.model.server_info.clear()
	table.model.catalog.clear()
	message.text = ""
	_update_host_status()


func _new_room() -> void:
	table.tools_ui.prefs.seats = ["human", "human", "human", "human"]
	table.tools_ui.new_game()


func _join(value: String) -> void:
	if waiting:
		return
	var target = parse_invite(value)
	if target.is_empty():
		message.text = table.model.native("올바른 방 초대 링크를 입력하세요. 관리자 링크는 초대 링크가 아닙니다.")
		return
	if owned.get("running", false) and not _own_origin(target.origin):
		_confirm("다른 서버에 참가", func(): _connect_invite(value, target))
	else:
		_connect_invite(value, target)


func _own_origin(origin: String) -> bool:
	return origin in [owned.get("origin", ""), owned.get("room_base", "")]


func _connect_invite(_value: String, target: Dictionary) -> void:
	message.text = table.model.native("친구의 방에 연결하고 있습니다…")
	_set_waiting(true)
	# Test the friend's server first. A bad invite must not stop our own host.
	var connected = await table.tools_ui.connect_server(target.origin, "", target.game, false)
	_set_waiting(false)
	if not connected or table.game_id != target.game:
		message.text = table.status.text
		return
	if owned.get("running", false) and not _own_origin(target.origin):
		var result = await _request("stop")
		if result.get("ok", false):
			owned = result
	show_table()
