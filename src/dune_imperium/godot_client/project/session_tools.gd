extends Node

var table: Control
var prefs: Dictionary = {}
var menu: MenuButton
var review: Dictionary = {}
var live_snapshot: Dictionary = {}
var review_serial = 0
var playback = false
var playback_unit = "turn"
var playback_interval = 1.0
var clock_anchor = 0
var clock_age = 0.0
var clock: Dictionary = {}
var clock_label: Label
var seat_clock_labels: Dictionary = {}
const PREFS_FILE = "res://../../../../local/godot-ui.json"
var prefs_file = PREFS_FILE
const OPTION_KEYS = ["leader_draft", "choam_module", "promo_cards", "bloodlines", "tech_module", "immortality", "go_to_11", "epic_game", "arrakeen_scouts"]
const OPTION_NAMES = ["html.opt_leader_draft", "html.opt_choam", "html.opt_promo", "html.opt_bloodlines", "html.opt_tech", "html.opt_immortality", "html.opt_go_to_11", "html.opt_epic_game", "html.opt_scouts"]
const KINDS = ["human", "app_ai", "app_ai_medium", "app_ai_easy", "search", "heuristic", "rollout", "rollout_strong", "random", "checkpoint"]


func setup(owner_table: Control) -> void:
	table = owner_table
	if FileAccess.file_exists(prefs_file):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(prefs_file))
		if parsed is Dictionary:
			prefs = parsed
	table.model.language = str(prefs.get("language", "ko"))
	clock_label = table._label(table.new_button.get_parent(), "", 12)
	clock_label.move_to_front()
	menu = MenuButton.new()
	menu.text = table.model.native("메뉴")
	table.new_button.get_parent().add_child(menu)
	refresh_menu()
	menu.get_popup().id_pressed.connect(_menu)
	var response = await table.api.call_json(HTTPClient.METHOD_GET, "/whoami")
	if response.ok:
		table.model.server_info = response.data
	table.market_scroll.get_parent().visible = not prefs.get("market_folded", false)


func refresh_menu() -> void:
	if menu == null:
		return
	menu.text = table.model.native("메뉴")
	var popup = menu.get_popup()
	popup.clear()
	for title in ["게임 목록 / 방", "원격 서버 연결", "플레이 설정", "도움말", "다시보기 / 관전", "방 링크 복사", "이번 방 나가기", "공용 카드 접기 / 펼치기", "플레이어 상세 접기 / 펼치기"]:
		popup.add_item(table.model.native(title))


func save_preferences() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(prefs_file.get_base_dir()))
	var file = FileAccess.open(prefs_file, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(prefs))


func text(key: String, values: Dictionary = {}) -> String:
	return table.model.ui(key, values)


func _dialog(title: String, dimensions = Vector2i(690, 520)) -> Array:
	table._hide_preview()
	var dialog = AcceptDialog.new()
	dialog.title = title
	dialog.ok_button_text = text("common.close")
	dialog.theme = table.theme
	dialog.set_meta("game_dialog", table.game_id)
	var root = VBoxContainer.new()
	root.custom_minimum_size = dimensions
	dialog.add_child(root)
	var body = table._scroll(root)
	table._attach_dialog(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()
	return [dialog, body]


func _menu(id: int) -> void:
	match id:
		0:
			if table.model.server_info.get("admin", true):
				games()
			else:
				lobby()
		1: connect_dialog()
		2: settings()
		3: help()
		4: enter_review()
		5:
			if not table.game_id.is_empty():
				var base = table.model.server_info.get("public_url")
				DisplayServer.clipboard_set((str(base) if base != null else table.api.base_url).trim_suffix("/") + "/#game=" + table.game_id)
		6: leave_game()
		7: toggle_market()
		8: toggle_seats()


func new_game() -> void:
	if table.busy or not table.model.server_info.get("admin", true):
		return
	var dialog = ConfirmationDialog.new()
	dialog.title = text("html.setup_title")
	dialog.ok_button_text = text("html.create_game")
	dialog.cancel_button_text = (table.model.native("취소") if table.model.language == "ko" else "Cancel")
	dialog.theme = table.theme
	dialog.set_meta("game_dialog", table.game_id)
	var root = VBoxContainer.new()
	root.custom_minimum_size = Vector2(720, 560)
	dialog.add_child(root)
	var body = table._scroll(root)
	table._label(body, text("html.seat_assignment_legend"), 17)
	var assignments = HBoxContainer.new()
	body.add_child(assignments)
	var selectors: Array[OptionButton] = []
	for seat in range(4):
		var stack = VBoxContainer.new()
		stack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		assignments.add_child(stack)
		table._label(stack, text("common.seat", {"seat": seat}), 14)
		var select = OptionButton.new()
		select.set_meta("seat_option", seat)
		select.fit_to_longest_item = false
		select.clip_text = true
		select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		for kind in KINDS:
			if kind == "search" and not table.model.server_info.get("search_ai", false):
				continue
			select.add_item(table.model.label("SEAT_KINDS", kind))
			select.set_item_metadata(select.item_count - 1, kind)
		var wanted = prefs.get("seats", ["human", "app_ai", "app_ai", "app_ai"])[seat]
		if table.model.server_info.get("access") == "remote" and not prefs.has("seats"):
			wanted = "human"
		for index in range(select.item_count):
			if select.get_item_metadata(index) == wanted:
				select.select(index)
		stack.add_child(select)
		selectors.append(select)
	var shuffle = CheckBox.new()
	shuffle.text = text("html.opt_shuffle_seats")
	shuffle.button_pressed = bool(prefs.get("shuffle", table.model.server_info.get("seating") == "random"))
	body.add_child(shuffle)
	var seed = LineEdit.new()
	seed.placeholder_text = text("html.opt_seed_label")
	seed.set_meta("seed_input", true)
	seed.visible = table.model.server_info.get("access", "open") == "open"
	body.add_child(seed)
	var checkpoint = LineEdit.new()
	checkpoint.placeholder_text = table.model.native("학습 파일의 서버 경로 / Server checkpoint path")
	body.add_child(checkpoint)
	var pace = OptionButton.new()
	for value in ["normal", "fast", "instant"]:
		pace.add_item(text("screens.ai_pace_" + value))
		pace.set_item_metadata(pace.item_count - 1, value)
	pace.select(["normal", "fast", "instant"].find(str(prefs.get("pace", "fast"))))
	body.add_child(pace)
	table._label(body, text("html.rule_options_legend"), 17)
	var switches: Dictionary = {}
	for index in range(OPTION_KEYS.size()):
		var key = OPTION_KEYS[index]
		var check = CheckBox.new()
		check.text = text(OPTION_NAMES[index])
		check.set_meta("game_option", key)
		check.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		check.button_pressed = bool(prefs.get("options", {}).get(key, key not in ["leader_draft", "arrakeen_scouts"]))
		body.add_child(check)
		switches[key] = check
	var sync_dependencies = func():
		switches.tech_module.disabled = not switches.bloodlines.button_pressed
		if switches.tech_module.disabled:
			switches.tech_module.button_pressed = false
		switches.go_to_11.disabled = not switches.immortality.button_pressed
		if switches.go_to_11.disabled:
			switches.go_to_11.button_pressed = false
	switches.bloodlines.toggled.connect(func(_checked): sync_dependencies.call())
	switches.immortality.toggled.connect(func(_checked): sync_dependencies.call())
	sync_dependencies.call()
	var presets = HBoxContainer.new()
	body.add_child(presets)
	for preset in [[table.model.native("기본판 / Base"), false], [table.model.native("웹 기본 설정 / Web defaults"), true]]:
		table._button(presets, preset[0], func():
			for key in switches:
				switches[key].button_pressed = preset[1] and key not in ["leader_draft", "arrakeen_scouts"]
			sync_dependencies.call()
		)
	table._attach_dialog(dialog)
	dialog.confirmed.connect(func():
		var config: Dictionary = {"seats": []}
		for select in selectors:
			var kind = str(select.get_item_metadata(select.selected))
			config.seats.append("checkpoint:" + checkpoint.text if kind == "checkpoint" else kind)
		prefs.seats = config.seats.duplicate()
		prefs.shuffle = shuffle.button_pressed
		if shuffle.button_pressed:
			config.seats.shuffle()
		for key in switches:
			config[key] = switches[key].button_pressed and not switches[key].disabled
		prefs.options = {}
		for key in switches:
			prefs.options[key] = config[key]
		prefs.pace = pace.get_item_metadata(pace.selected)
		var chosen_seed: Variant = int(seed.text) if seed.visible and seed.text.is_valid_int() else null
		save_preferences()
		table._create_game(chosen_seed, config.leader_draft, prefs.pace, config)
		dialog.queue_free()
	)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered()


func games() -> void:
	var response = await table.api.call_json(HTTPClient.METHOD_GET, "/games")
	if not table._accept(response):
		return
	var parts = _dialog(text("html.game_list_title"))
	for game in response.data:
		var row = HBoxContainer.new()
		parts[1].add_child(row)
		var button = table._button(row, "%s · %s" % [game.game_id.left(8), text("common.finished") if game.finished else text("screens.round_number", {"round": int(game.round_number)})], func():
			parts[0].queue_free()
			table._adopt_game(str(game.game_id))
		)
		button.set_meta("game_id", game.game_id)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if table.model.server_info.get("admin", false):
			var remove = table._button(row, text("screens.delete_button"), func(): delete_game(str(game.game_id), parts[0]))
			remove.set_meta("delete_game_id", game.game_id)
	if not table.game_id.is_empty():
		table._button(parts[1], text("html.open_lobby"), lobby)
	table._button(parts[1], table.model.native("새로고침"), func(): parts[0].queue_free(); games())


func delete_game(id: String, list_dialog: Window) -> void:
	var dialog = ConfirmationDialog.new()
	dialog.title = text("screens.delete_confirm_button")
	dialog.dialog_text = table.model.native("이 게임을 삭제하시겠습니까? 저장한 파일은 별도로 남습니다.")
	dialog.ok_button_text = text("screens.delete_button")
	dialog.cancel_button_text = table.model.native("취소")
	dialog.theme = table.theme
	dialog.set_meta("delete_game_id", id)
	table._attach_dialog(dialog)
	dialog.confirmed.connect(func():
		var response = await table.api.call_json(HTTPClient.METHOD_DELETE, "/games/" + id)
		if table._accept(response):
			if table.game_id == id:
				leave_game()
			list_dialog.hide()
			list_dialog.queue_free()
			games()
		dialog.queue_free()
	)
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered(Vector2i(450, 170))


func connect_dialog() -> void:
	var parts = _dialog(table.model.native("서버 / Server"), Vector2i(620, 190))
	var url = LineEdit.new()
	url.placeholder_text = "http://host:port/#game=…"
	parts[1].add_child(url)
	table._button(parts[1], table.model.native("접속 / Connect"), func():
		connect_url(url.text)
		parts[0].queue_free()
	)


func connect_url(url: String) -> bool:
	if table.busy:
		table.status.text = table.model.native("현재 선택을 처리하고 있습니다. 잠시 후 연결하세요.")
		return false
	var clean = url.strip_edges()
	if not clean.begins_with("http://") and not clean.begins_with("https://"):
		table.status.text = table.model.native("http:// 또는 https:// 주소를 입력하세요. / Enter an HTTP(S) URL.")
		return false
	var authority = clean.get_slice("#", 0).trim_suffix("/")
	var origin = authority.get_slice("/", 0) + "//" + authority.get_slice("/", 2)
	var fragment = clean.get_slice("#", 1)
	leave_game()
	table.api.base_url = origin
	var admin_key = ""
	var wanted = ""
	for pair in fragment.split("&"):
		if pair.get_slice("=", 0) == "admin":
			admin_key = pair.get_slice("=", 1).uri_decode()
		elif pair.get_slice("=", 0) == "game":
			wanted = pair.get_slice("=", 1).uri_decode()
	if not admin_key.is_empty():
		var auth = await table.api.call_json(HTTPClient.METHOD_POST, "/auth/admin", {"key": admin_key})
		if not table._accept(auth):
			return false
	var info = await table.api.call_json(HTTPClient.METHOD_GET, "/whoami")
	var catalog = await table.api.call_json(HTTPClient.METHOD_GET, "/catalog")
	if not table._accept(info) or not table._accept(catalog):
		return false
	table.model.server_info = info.data
	table.model.catalog = catalog.data
	table.board.textures.clear()
	table.board.board_texture = table.api.texture(str(catalog.data.board_image)) if catalog.data.get("board_image") != null else null
	if not wanted.is_empty():
		await table._adopt_game(wanted)
		if table.model.active_seat < 0 and not table.model.summary().get("finished", false):
			lobby()
	else:
		games()
	return true


func lobby() -> void:
	if table.game_id.is_empty():
		return
	var parts = _dialog(text("html.lobby_title"), Vector2i(650, 360))
	var name = LineEdit.new()
	name.max_length = 20
	name.text = str(prefs.get("name", ""))
	name.placeholder_text = text("html.lobby_name_label")
	parts[1].add_child(name)
	for player in table.model.summary().get("players", []):
		var seat = int(player.seat)
		var row = HBoxContainer.new()
		parts[1].add_child(row)
		var who = str(player.name) if player.name != null else text("common.seat", {"seat": seat})
		table._label(row, who + (" ●" if player.online else " ○"), 15).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if player.kind != "human":
			table._label(row, table.model.label("SEAT_KINDS", str(player.kind)), 14)
		elif seat in table.model.owned_seats:
			table._button(row, table.model.native("입장 / Enter"), func(): parts[0].queue_free(); table._sync(seat))
			table._button(row, table.model.native("자리 비우기 / Release"), func(): _release_seat(seat, parts[0]))
		elif not player.claimed:
			table._button(row, table.model.native("앉기 / Sit"), func():
				var response = await table.api.call_json(HTTPClient.METHOD_POST, "/games/" + table.game_id + "/seats/" + str(seat) + "/claim", {"name": name.text})
				if table._accept(response):
					prefs.name = name.text
					save_preferences()
					parts[0].queue_free()
					table.doorbell.start(table.game_id)
					await table._sync(seat)
			)
		elif table.model.server_info.get("admin", false):
			table._button(row, table.model.native("자리 비우기 / Release"), func(): _release_seat(seat, parts[0]))


func _release_seat(seat: int, dialog: Window) -> void:
	var response = await table.api.call_json(HTTPClient.METHOD_POST, "/games/" + table.game_id + "/seats/" + str(seat) + "/release")
	if table._accept(response):
		dialog.queue_free()
		await table._sync(-1)
		lobby()


func leave_game() -> void:
	close_game_dialogs()
	playback = false
	review.clear()
	table.generation += 1
	table.game_id = ""
	table.doorbell.stop()
	table.model.adopt({})
	clock.clear()
	clock_label.text = ""
	table.inspect_ref = ""
	table._render()


func settings() -> void:
	var parts = _dialog(table.model.native("플레이 설정 / Preferences"), Vector2i(650, 500))
	var language = OptionButton.new()
	language.add_item("한국어")
	language.add_item("English")
	language.select(0 if table.model.language == "ko" else 1)
	parts[1].add_child(language)
	language.item_selected.connect(func(index):
		table.model.language = "ko" if index == 0 else "en"
		prefs.language = table.model.language
		save_preferences()
		table._render()
		parts[0].hide()
		parts[0].queue_free()
		settings()
	)
	var pace = OptionButton.new()
	for value in ["normal", "fast", "instant"]:
		pace.add_item(text("screens.ai_pace_" + value))
		pace.set_item_metadata(pace.item_count - 1, value)
	pace.select(["normal", "fast", "instant"].find(str(table.model.summary().get("ai_pace", prefs.get("pace", "fast")))))
	parts[1].add_child(pace)
	pace.disabled = table.game_id.is_empty() or not table.model.server_info.get("admin", false)
	pace.item_selected.connect(func(index):
		var value = pace.get_item_metadata(index)
		var response = await table.api.call_json(HTTPClient.METHOD_POST, "/games/" + table.game_id + "/ai-pace", {"pace": value})
		if table._accept(response):
			prefs.pace = value
			save_preferences()
			await table._sync()
	)
	table._button(parts[1], table.model.native("개인 배치 초기화"), table.layout_ui.reset)
	table._button(parts[1], table.model.native("다음 실행의 서버 설정"), host_settings)
	for pair in [["log_follow", "로그 자동 따라가기", true], ["animations", "연출 켜기", true], ["reduced_motion", "움직임 줄이기", false], ["sound", "효과음 켜기", true]]:
		var check = CheckBox.new()
		check.text = table.model.native(pair[1])
		check.button_pressed = prefs.get(pair[0], pair[2])
		parts[1].add_child(check)
		check.toggled.connect(func(value): prefs[pair[0]] = value; save_preferences())
	table._label(parts[1], table.model.native("효과음 음량"), 14)
	var volume = HSlider.new()
	volume.min_value = 0
	volume.max_value = 1
	volume.step = 0.05
	volume.value = float(prefs.get("volume", 0.35))
	parts[1].add_child(volume)
	volume.value_changed.connect(func(value): prefs.volume = value; save_preferences())
	table._button(parts[1], table.model.native("효과음 들어보기"), func(): table.effects.sound("decision"))
	table._label(parts[1], table.model.native("손패·책략을 드래그해서 순서를 바꾸고 열 사이를 드래그해서 너비를 조절하세요."), 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func host_settings() -> void:
	var config = prefs.get("host", {})
	var parts = _dialog(table.model.native("다음 실행의 서버 설정"), Vector2i(710, 490))
	table._label(parts[1], table.model.native("저장 후 앱을 다시 실행하면 적용됩니다."), 14)
	var mode = OptionButton.new()
	for title in ["혼자 / 같은 컴퓨터에서 플레이", "친구 초대 서버"]:
		mode.add_item(table.model.native(title))
	mode.select(1 if config.get("mode") == "remote" else 0)
	parts[1].add_child(mode)
	var fields: Dictionary = {}
	for pair in [["bind", "서버가 받을 주소", "0.0.0.0"], ["public_url", "친구에게 보낼 서버 주소", "http://192.168.1.10:8000"], ["checkpoint", "선택: 학습 체크포인트 파일", ""], ["python", "선택: 학습 런타임 실행 파일", ""]]:
		table._label(parts[1], table.model.native(pair[1]), 14)
		var row = HBoxContainer.new()
		parts[1].add_child(row)
		var input = LineEdit.new()
		input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		input.text = str(config.get(pair[0], pair[2] if pair[0] == "bind" else ""))
		input.placeholder_text = pair[2]
		row.add_child(input)
		fields[pair[0]] = input
		if pair[0] in ["checkpoint", "python"]:
			table._button(row, table.model.native("파일 선택"), func():
				var file = FileDialog.new()
				file.access = FileDialog.ACCESS_FILESYSTEM
				file.file_mode = FileDialog.FILE_MODE_OPEN_FILE
				file.use_native_dialog = true
				table.add_child(file)
				file.file_selected.connect(func(path): input.text = path; file.queue_free())
				file.canceled.connect(file.queue_free)
				file.popup_centered(Vector2i(850, 600))
			)
	table._label(parts[1], table.model.native("포트"), 14)
	var port = SpinBox.new()
	port.min_value = 1
	port.max_value = 65535
	port.value = int(config.get("port", 8000))
	parts[1].add_child(port)
	var message = table._label(parts[1], "", 13)
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	table._button(parts[1], table.model.native("저장"), func():
		for key in ["python", "checkpoint"]:
			if not fields[key].text.is_empty() and not FileAccess.file_exists(fields[key].text):
				message.text = table.model.native("선택한 파일을 찾지 못했습니다.")
				return
		if mode.selected == 1 and (fields.bind.text.strip_edges().is_empty() or not (fields.public_url.text.begins_with("http://") or fields.public_url.text.begins_with("https://"))):
			message.text = table.model.native("서버가 받을 주소와 친구에게 보낼 HTTP(S) 주소를 입력하세요.")
			return
		prefs.host = {"mode": "remote" if mode.selected == 1 else "local", "bind": fields.bind.text.strip_edges(), "public_url": fields.public_url.text.strip_edges(), "port": int(port.value), "checkpoint": fields.checkpoint.text.strip_edges(), "python": fields.python.text.strip_edges()}
		save_preferences()
		parts[0].hide()
		parts[0].queue_free()
	)


func help() -> void:
	var parts = _dialog(text("help.title"))
	for key in table.model.words.get("ui", {}):
		if not str(key).begins_with("help.") or key == "help.title":
			continue
		table._label(parts[1], text(key), 16).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for key in table.model.words.get("terms", {}):
		table._label(parts[1], "%s / %s" % [table.model.words.terms[key].ko, table.model.words.terms[key].en], 14)


func enter_review() -> void:
	if table.game_id.is_empty() or not table.model.summary().get("finished", false):
		table.status.text = table.model.native("끝난 게임을 고르면 다시보기와 관전을 할 수 있습니다. / Select a finished game.")
		return
	await _review_meta(maxi(0, table.model.active_seat))


func anchor_clock(snapshot: Dictionary) -> void:
	var value = snapshot.get("summary", {}).get("clock")
	clock = value if value is Dictionary else {}
	clock_age = float(snapshot.get("clock_age_ms", 0))
	clock_anchor = Time.get_ticks_msec()


func _process(_delta: float) -> void:
	if table == null or clock.is_empty() or not review.is_empty():
		return
	clock_label.show()
	var reading = table.model.clock_reading(clock, clock_age + Time.get_ticks_msec() - clock_anchor)
	clock_label.text = table.model.clock_text(reading.elapsed)
	clock_label.tooltip_text = text("clock.game_title")
	for seat in seat_clock_labels:
		var label = seat_clock_labels[seat]
		if is_instance_valid(label):
			label.text = table.model.clock_text(reading.seats[int(seat)])


func save_dialog() -> void:
	if table.game_id.is_empty() or table.busy:
		return
	var parts = _dialog(text("html.save_game"), Vector2i(600, 170))
	var name = LineEdit.new()
	name.placeholder_text = text("session.save_name_prompt")
	parts[1].add_child(name)
	table._button(parts[1], text("html.save_game"), func():
		var response = await table._save_game(name.text if not name.text.is_empty() else null)
		if response.ok:
			parts[0].queue_free()
	)


func vp_ledger(seat: int) -> void:
	if table.game_id.is_empty():
		return
	var game = table.game_id
	var response = await table.api.call_json(HTTPClient.METHOD_GET, "/games/" + game + "/vp-ledger")
	if game != table.game_id or not table._accept(response):
		return
	var parts = _dialog(text("panels.vp_ledger_title", {"name": table.model.seat_name(seat), "points": table.model.view().get("players", [])[seat].victory_points}), Vector2i(660, 460))
	table._label(parts[1], text("panels.vp_ledger_note"), 14)
	table._label(parts[1], "%s: %d" % [text("common.start") if table.model.words.ui.has("common.start") else table.model.native("시작 / Start"), int(response.data.start[seat])], 15)
	var shown = table.model.snapshot.get("log", {}).get("entries", [])
	var last_index = int(shown[-1].index) if not shown.is_empty() else -1
	for row in response.data.get("entries", []):
		if int(row.seat) != seat or int(row.index) > last_index:
			continue
		var cause = ""
		for entry in shown:
			if int(entry.index) == int(row.index):
				cause = table.model.describe(entry) if entry.get("type") == "action" else " · ".join(_event_names(entry))
		var button = table._button(parts[1], "%d R · %s → %d\n%s" % [int(row.round), ("+" if int(row.delta) >= 0 else "") + str(int(row.delta)), int(row.total), cause], func():
			parts[0].queue_free()
			focus_log(int(row.index))
		)
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT


func _event_names(entry: Dictionary) -> PackedStringArray:
	var names: PackedStringArray = []
	for event in entry.get("events", []):
		names.append(table.model.label("EVENT_LABELS", str(event.get("kind", ""))))
	return names


func focus_log(index: int) -> void:
	table._set_tab("log")
	# Explicit ledger navigation wins over the log's pending follow/restore.
	var serial = int(table.content.get_meta("log_render_serial", 0)) + 1
	table.content.set_meta("log_render_serial", serial)
	await get_tree().process_frame
	await get_tree().process_frame
	if table.tab != "log" or int(table.content.get_meta("log_render_serial", -1)) != serial:
		return
	for line in table.content.get_children():
		if int(line.get_meta("log_index", -1)) == index:
			table.content.get_parent().ensure_control_visible(line)
			line.modulate = Color("f7d49a")
			return


func _review_meta(seat: int, cursor = -1, play = false) -> bool:
	var game = table.game_id
	var response = await table.api.call_json(HTTPClient.METHOD_GET, "/games/" + game + "/review?seat=" + str(seat))
	if table.game_id != game or not table._accept(response):
		return false
	if review.is_empty():
		live_snapshot = table.model.snapshot.duplicate(true)
	playback = false
	review = {"meta": response.data, "seat": seat, "cursor": int(response.data.step_count) if cursor < 0 else cursor}
	var accepted = await review_goto(int(review.cursor))
	if accepted and play:
		playback = true
		_playback_next()
	return accepted


func review_goto(cursor: int) -> bool:
	if review.is_empty():
		return false
	review_serial += 1
	var serial = review_serial
	var game = table.game_id
	cursor = clampi(cursor, 0, int(review.meta.step_count))
	var response = await table.api.call_json(HTTPClient.METHOD_GET, "/games/" + game + "/review/" + str(cursor) + "?seat=" + str(review.seat))
	if serial != review_serial or game != table.game_id or review.is_empty():
		return false
	if not table._accept(response):
		playback = false
		return false
	close_game_dialogs()
	review.cursor = cursor
	var data = live_snapshot.duplicate(true)
	data.summary.round_number = response.data.round_number
	data.summary.phase = response.data.phase
	data.summary.revision = response.data.view.get("revision", cursor)
	data.view = response.data.view
	data.actions = null
	data.log = {"entries": table.model.reviewed_log(review.meta, cursor), "count": cursor, "seat": review.seat}
	table.model.adopt(data)
	table._render()
	return true


func render_review(parent: VBoxContainer) -> void:
	clock_label.hide()
	table.finish_button.disabled = true
	table.selection.text = text("review.before_game_start") if int(review.cursor) == 0 else "%d / %d" % [int(review.cursor), int(review.meta.step_count)]
	var seats = OptionButton.new()
	for seat in range(4):
		seats.add_item(table.model.seat_name(seat))
	seats.select(int(review.seat))
	parent.add_child(seats)
	seats.item_selected.connect(func(seat): _review_meta(seat, int(review.cursor), playback))
	var controls = HBoxContainer.new()
	parent.add_child(controls)
	for pair in [["|◀", 0], ["◀", int(review.cursor) - 1], ["▶", int(review.cursor) + 1], ["▶|", int(review.meta.step_count)]]:
		var button = table._button(controls, pair[0], func(): playback = false; review_goto(pair[1]))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var slider = HSlider.new()
	slider.min_value = 0
	slider.max_value = int(review.meta.step_count)
	slider.step = 1
	slider.value = int(review.cursor)
	parent.add_child(slider)
	slider.set_meta("review_slider", true)
	var dragging = {"active": false}
	slider.drag_started.connect(func(): dragging.active = true)
	slider.value_changed.connect(func(value):
		if not dragging.active:
			playback = false
			review_goto(int(value))
	)
	slider.drag_ended.connect(func(changed):
		dragging.active = false
		if changed:
			playback = false
			review_goto(int(slider.value))
	)
	var own = HBoxContainer.new()
	parent.add_child(own)
	table._button(own, text("review.prev_own_action", {"own": text("review.own_mine")}), _jump_own.bind(-1))
	table._button(own, text("review.next_own_action", {"own": text("review.own_mine")}), _jump_own.bind(1))
	table._button(parent, text("review.pause") if playback else text("review.play"), func():
		playback = not playback
		if playback:
			_playback_next()
		table._render_choices()
	)
	var unit = OptionButton.new()
	unit.add_item(text("html.review_unit_turn"))
	unit.add_item(text("html.review_unit_step"))
	unit.select(0 if playback_unit == "turn" else 1)
	parent.add_child(unit)
	unit.item_selected.connect(func(index): playback_unit = "turn" if index == 0 else "step")
	var interval = OptionButton.new()
	for value in [0.25, 0.5, 1.0, 2.0, 4.0]:
		interval.add_item(str(value) + " s")
		interval.set_item_metadata(interval.item_count - 1, value)
		if is_equal_approx(playback_interval, value):
			interval.select(interval.item_count - 1)
	parent.add_child(interval)
	interval.item_selected.connect(func(index): playback_interval = interval.get_item_metadata(index))
	table._button(parent, text("html.review_exit"), exit_review)
	if int(review.cursor) > 0:
		var step = review.meta.steps[int(review.cursor) - 1]
		var label = table._label(parent, table.model.describe(step) if step.get("type") == "action" else table.model.label("EVENT_LABELS", str(step.get("decision_id", ""))), 14)
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _jump_own(direction: int) -> void:
	playback = false
	var cursor = int(review.cursor) + direction
	while cursor >= 1 and cursor <= review.meta.steps.size():
		var step = review.meta.steps[cursor - 1]
		if step.get("type") == "action" and int(step.actor) == int(review.seat):
			review_goto(cursor)
			return
		cursor += direction


func _playback_next() -> void:
	if not playback or review.is_empty():
		return
	var game = table.game_id
	var serial = review_serial
	await get_tree().create_timer(playback_interval).timeout
	if not playback or review.is_empty() or table.game_id != game or serial != review_serial:
		return
	var cursor = int(review.cursor) + 1
	if playback_unit == "turn":
		for stop in table.model.turn_stops(review.meta.steps):
			if int(stop) > int(review.cursor):
				cursor = int(stop)
				break
	if cursor > int(review.meta.step_count):
		playback = false
		table._render_choices()
		return
	if await review_goto(cursor):
		_playback_next()


func exit_review() -> void:
	playback = false
	review_serial += 1
	var data = live_snapshot.duplicate(true)
	if not data.get("view") is Dictionary:
		var response = await table.api.call_json(HTTPClient.METHOD_GET, "/games/" + table.game_id + "/review/" + str(review.meta.step_count) + "?seat=" + str(review.seat))
		if not table._accept(response):
			return
		data.view = response.data.view
	review.clear()
	table.model.adopt(data)
	table._render()


func close_game_dialogs(keep_piles = false) -> void:
	for child in table.find_children("*", "Window", true, false):
		if child.has_meta("game_dialog") and not child.is_queued_for_deletion() and not (keep_piles and child.has_meta("pile_viewer")):
			child.hide()
			child.queue_free()


func toggle_market() -> void:
	prefs.market_folded = not prefs.get("market_folded", false)
	table.market_scroll.get_parent().visible = not prefs.market_folded
	save_preferences()
	table._hide_preview()
	table._fit_columns()


func toggle_seats() -> void:
	prefs.seat_details = not prefs.get("seat_details", false)
	save_preferences()
	table._render_seats()


func save_delete_button(parent: Node, save_id: String, list_dialog: Window) -> void:
	var remove = table._button(parent, text("screens.delete_button"), func():
		var dialog = ConfirmationDialog.new()
		dialog.title = text("screens.delete_confirm_button")
		dialog.dialog_text = text("screens.delete_confirm_button")
		dialog.ok_button_text = text("screens.delete_button")
		dialog.cancel_button_text = table.model.native("취소") if table.model.language == "ko" else "Cancel"
		dialog.theme = table.theme
		table._attach_dialog(dialog)
		dialog.confirmed.connect(func():
			var response = await table.api.call_json(HTTPClient.METHOD_DELETE, "/saves/" + save_id.uri_encode())
			if table._accept(response):
				list_dialog.hide()
				list_dialog.queue_free()
				table._show_saves()
			dialog.queue_free()
		)
		dialog.canceled.connect(dialog.queue_free)
		dialog.popup_centered(Vector2i(420, 150))
	)
	remove.set_meta("delete_save_id", save_id)
