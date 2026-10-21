extends Node

# Developer-only entry: exercised through the real launcher mailbox and server.
var table: Control
var checks = 0
var failed = false
var captures: Array = []


func check(condition: bool, title: String) -> bool:
	checks += 1
	if not condition:
		failed = true
		push_error("GODOT_MENU_FAILED: " + title)
		get_tree().quit(1)
	return condition


func settled() -> void:
	for frame in range(3):
		await get_tree().process_frame
	while table.front_ui.waiting or table.busy or table.refreshing:
		await get_tree().process_frame
	await get_tree().process_frame


func action(key: String, target: Control = null) -> Button:
	if target == null:
		target = table
	for button in target.front_ui.find_children("*", "Button", true, false):
		if button.get_meta("front_action", "") == key:
			return button
	return null


func close_dialogs(target: Control = null) -> void:
	if target == null:
		target = table
	for window in target.find_children("*", "Window", true, false):
		if window.visible:
			window.hide()
			window.queue_free()


func create_from_dialog() -> bool:
	for window in table.find_children("*", "ConfirmationDialog", true, false):
		if window.visible:
			window.confirmed.emit()
			await settled()
			return not table.game_id.is_empty()
	return false


func capture(name: String) -> void:
	if table.capture_dir.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var path = table.capture_dir.path_join(name + ".png")
	check(get_viewport().get_texture().get_image().save_png(path) == OK, "capture " + name)
	captures.append(name)


func run(owner_table: Control) -> void:
	table = owner_table
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 160
	timer.timeout.connect(func(): check(false, "menu watchdog"))
	add_child(timer)
	timer.start()
	await settled()
	var front = table.front_ui
	if not check(front.visible and front.page == "home" and not table.table_surface.visible and table.api.base_url.is_empty(), "launch opens the four-choice main menu without a server connection"):
		return
	var state = await front._request("inspect")
	if not check(state.ok and not state.running, "launch and address discovery have not started a server"):
		return
	var original_size = get_window().size
	for language in ["ko", "en"]:
		table.model.language = language
		table._render()
		await settled()
		for key in ["single", "multi", "settings", "quit"]:
			var rectangle = action(key).get_global_rect()
			check(get_viewport().get_visible_rect().encloses(rectangle), "home action remains inside the window")
			check(action(key) != null and action(key).visible and not action(key).disabled, "home action " + language + " " + key)
		await capture("main-menu-" + language)
		get_window().size = Vector2i(1100, 740)
		await settled()
		for key in ["single", "multi", "settings", "quit"]:
			check(get_viewport().get_visible_rect().encloses(action(key).get_global_rect()), "main menu fits a narrow window")
		await capture("main-menu-" + language + "-narrow")
		get_window().size = original_size
		await settled()
		action("settings").pressed.emit()
		await settled()
		check(not table.find_children("*", "AcceptDialog", true, false).is_empty(), "preferences are available before starting a server")
		await capture("settings-" + language)
		close_dialogs()
	table.model.language = "ko"
	table._render()
	action("multi").pressed.emit()
	await settled()
	check(front.host_status != null and front.start_button != null, "multiplayer opens server settings immediately")
	check(front.page == "multi", "multiplayer is an explicit route")
	await capture("multiplayer")
	action("join").pressed.emit()
	check(front.page == "join", "joining has a dedicated link field")
	for invalid in ["", "http://example.com", "file:///tmp/save", "https://user:secret@example.com/#game=x", "http://example.com:65536/#game=x", "https://example.com/#admin=secret", "https://example.com/#game=../secret"]:
		check(front.parse_invite(invalid).is_empty(), "reject invalid invitation")
	front.fields.invite_url.text = "not a link"
	action("connect").pressed.emit()
	await settled()
	check(not front.message.text.is_empty() and table.api.base_url.is_empty(), "bad invite stays on the join page without starting anything")
	await capture("join-error")
	check(front.parse_invite(" https://example.com:8123/#game=abc-123 ") == {"origin": "https://example.com:8123", "game": "abc-123"}, "parse a copied invitation")
	check(not front.parse_invite("http://[::1]:8123/#game=abc").is_empty(), "IPv6 invitation")
	front.show_page("single")
	action("new_single").pressed.emit()
	await settled()
	if not check(front.owned.get("mode") == "local" and table.model.server_info.get("access") == "open", "single player starts its own loopback server"):
		return
	if not check(await create_from_dialog(), "single-player setup creates a game"):
		return
	await settled()
	check(not front.visible and table.table_surface.visible, "entering a game shows the table")
	check(table.model.summary().seats.count("human") == 1, "single-player setup defaults to one human and three AI seats")
	front.show_page("home")
	check(action("resume") != null, "the main menu can return to a running game")
	front.show_page("host")
	await settled()
	var local_port = int(front.owned.port)
	front.port.value = local_port
	front.fields.bind.text = "127.0.0.1"
	front.fields.public_url.text = "http://127.0.0.1:" + str(local_port)
	action("start_server").pressed.emit()
	for dialog in front.find_children("*", "ConfirmationDialog", true, false):
		dialog.confirmed.emit()
	await settled()
	if not check(front.owned.get("mode") == "remote" and table.model.server_info.get("admin", false), "host switches the owned server immediately and authenticates privately"):
		return
	check(front.copy_button.disabled and front.invite.text.is_empty(), "no broken invitation is offered before a room exists")
	await capture("host-running")
	action("new_room").pressed.emit()
	await settled()
	if not check(await create_from_dialog(), "the host creates a room from server settings"):
		return
	await settled()
	check(table.model.summary().seats.count("human") == 4, "multiplayer defaults to human seats")
	var game = table.game_id
	close_dialogs()
	front.show_page("host")
	await settled()
	var invite = front.invite.text
	check(not front.copy_button.disabled and invite.ends_with("/#game=" + game) and not "admin" in invite, "invite is a guest room link with no administrator credential")
	await capture("host-invite")
	table.model.language = "en"
	table._render()
	await settled()
	await capture("host-invite-en")
	get_window().size = Vector2i(1100, 740)
	await settled()
	for key in ["start_server", "copy_invite", "new_room"]:
		check(get_viewport().get_visible_rect().encloses(action(key).get_global_rect()), "host controls fit a narrow window")
	await capture("host-invite-en-narrow")
	get_window().size = original_size
	table.model.language = "ko"
	table._render()
	await settled()
	var before = await front._request("inspect")
	front.show_page("join")
	front.fields.invite_url.text = "http://127.0.0.1:" + str(local_port) + "/#game=missing-room"
	action("connect").pressed.emit()
	await settled()
	check(table.game_id == game and front.visible, "an expired invitation preserves the current game and host")
	var after = await front._request("inspect")
	check(before.origin == after.origin and after.running, "failed join did not stop the server")
	# A second native client is an actual unauthenticated guest, not the host.
	var guest = load("res://main.tscn").instantiate()
	guest.set_meta("menu_test_guest", true)
	add_child(guest)
	for frame in range(8):
		await get_tree().process_frame
	guest.api.cookies.entries.clear()
	guest.api.cookie_file = table.api.cookie_file + "-guest"
	guest.front_ui.show_page("join")
	guest.front_ui.fields.invite_url.text = invite
	action("connect", guest).pressed.emit()
	while guest.front_ui.waiting or guest.busy or guest.refreshing:
		await get_tree().process_frame
	check(guest.game_id == game and not guest.model.server_info.get("admin", true), "the invitation joins the room as a guest")
	var denied = await guest.api.call_json(HTTPClient.METHOD_POST, "/games", {})
	check(int(denied.code) == 403, "guest receives no host permissions")
	await capture("guest-lobby")
	for input in guest.find_children("*", "LineEdit", true, false):
		if input.max_length == 20:
			input.text = "테스트 친구"
			input.text_changed.emit(input.text)
	var sat = false
	for button in guest.find_children("*", "Button", true, false):
		if button.text == guest.model.native("앉기 / Sit") and not button.disabled:
			button.pressed.emit()
			sat = true
			break
	var claim_deadline = Time.get_ticks_msec() + 5000
	while (guest.model.owned_seats.is_empty() or guest.refreshing) and Time.get_ticks_msec() < claim_deadline:
		await get_tree().process_frame
	if not check(sat and not guest.model.owned_seats.is_empty(), "the joined guest can claim a human seat"):
		print("GUEST_CLAIM ", JSON.stringify({"sat": sat, "owned": guest.model.owned_seats, "refreshing": guest.refreshing, "busy": guest.busy, "status": guest.status.text}))
	guest.doorbell.stop()
	guest.queue_free()
	await get_tree().process_frame
	front.show_page("host")
	await settled()
	action("stop_server").pressed.emit()
	for dialog in front.find_children("*", "ConfirmationDialog", true, false):
		dialog.confirmed.emit()
	await settled()
	check(not front.owned.get("running", true) and table.api.base_url.is_empty(), "stop server releases the owned host without restarting the app")
	var dropped = table.Api.new()
	dropped.base_url = before.origin
	add_child(dropped)
	var disconnected = await dropped.call_json(HTTPClient.METHOD_GET, "/whoami")
	check(not disconnected.ok, "a closed server returns a clean connection failure without a JSON engine error")
	dropped.queue_free()
	front.show_page("home")
	check(action("quit") != null, "quit remains available after stopping the server")
	if not failed:
		print("GODOT_MENU_OK ", JSON.stringify({"checks": checks, "captures": captures, "mode_changes": 2, "guest_join": true}))
		action("quit").pressed.emit()
