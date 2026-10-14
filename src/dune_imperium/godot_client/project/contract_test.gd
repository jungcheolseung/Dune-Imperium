extends SceneTree

const Api = preload("res://api.gd")
var table: Control
var host: Node
var peer: Node
var checks = 0
var failed = false
var mode = "open"
var url = ""


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--mode="):
			mode = argument.trim_prefix("--mode=")
		elif argument.begins_with("--server="):
			url = argument.trim_prefix("--server=")
	call_deferred("run")


func client(profile: String) -> Node:
	var api = Api.new()
	api.base_url = url
	api.cookie_file = "res://../../../../tmp/godot/contracts/" + profile + "-cookies.json"
	api.add_to_group("contract-client")
	root.add_child(api)
	# Start isolated; persistence is tested explicitly below.
	api.cookies.entries.clear()
	return api


func check(condition: bool, message: String) -> bool:
	checks += 1
	if not condition:
		failed = true
		push_error("GODOT_CONTRACT_FAILED: " + message)
		quit(1)
	return condition


func ready_table() -> void:
	table = load("res://main.tscn").instantiate()
	root.add_child(table)
	while table.model.catalog.is_empty() or table.tools_ui.table == null:
		await process_frame
	await process_frame
	await process_frame


func wait_ready() -> void:
	while table.busy or table.refreshing:
		await process_frame
	await process_frame
	await process_frame


func action_buttons(node: Node) -> Array:
	var found: Array = []
	for child in node.get_children():
		if child is Button and child.has_meta("action_index"):
			found.append(child)
		found.append_array(action_buttons(child))
	return found


func play_first() -> bool:
	var action = table.model.actions()[0]
	if action.action_id == "agent_turn":
		table._choose_ref(action.arguments.card_id)
		table._choose_ref(action.arguments.space_id)
	await process_frame
	if action.action_id in table.Model.END_ACTIONS:
		table.finish_button.pressed.emit()
	else:
		var found = false
		for button in action_buttons(table.content):
			if int(button.get_meta("action_index")) == int(action.index):
				button.pressed.emit()
				found = true
				break
		if not check(found, "offered action has no native control"):
			return false
		if action.get("sent_by_turn_end", false):
			table.finish_button.pressed.emit()
	await wait_ready()
	return not failed


func run() -> void:
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 150
	timer.timeout.connect(func(): check(false, "contract timeout"))
	root.add_child(timer)
	timer.start()
	host = client(mode + "-host")
	peer = client(mode + "-peer")
	var info = await host.call_json(HTTPClient.METHOD_GET, "/whoami")
	if not check(info.ok and info.data.access == mode, "server mode"):
		return
	if mode == "remote":
		var denied = await peer.call_json(HTTPClient.METHOD_POST, "/games", {})
		if not check(int(denied.code) == 403, "unauthorized guest creates no game"):
			return
		var login = await host.call_json(HTTPClient.METHOD_POST, "/auth/admin", {"key": "a".repeat(48)})
		if not check(login.ok and not host.cookies.header(url, "/games", Time.get_unix_time_from_system()).is_empty(), "administrator cookie stored from HTTP response"):
			return
	var created = await host.call_json(HTTPClient.METHOD_POST, "/games", {"seats": ["app_ai", "human", "app_ai", "human"], "game_seed": 11, "ai_pace": "instant"})
	if not check(created.ok, "non-first human game"):
		return
	var game = str(created.data.game_id)
	if mode == "remote":
		var denied = await peer.call_json(HTTPClient.METHOD_GET, "/games/" + game + "/snapshot?seat=1")
		if not check(int(denied.code) == 403, "unclaimed hand stays private"):
			return
		var claim = await peer.call_json(HTTPClient.METHOD_POST, "/games/" + game + "/seats/1/claim", {"name": "한글 플레이어"})
		if not check(claim.ok, "Korean name and seat claim"):
			return
		var resumed = Api.new()
		resumed.base_url = url
		resumed.cookie_file = peer.cookie_file
		root.add_child(resumed)
		var you = await resumed.call_json(HTTPClient.METHOD_GET, "/games/" + game + "/me")
		if not check(you.ok and you.data.seats.size() == 1 and int(you.data.seats[0]) == 1, "restart restores only its claimed seat"):
			return
		var other = await peer.call_json(HTTPClient.METHOD_GET, "/games/" + game + "/snapshot?seat=3")
		if not check(int(other.code) == 403, "another human's hand is not available"):
			return
	await ready_table()
	table.api.cookies.entries = peer.cookies.entries.duplicate(true)
	if not await table._adopt_game(game):
		check(false, "native game adopt")
		return
	await wait_ready()
	if not check(table.model.active_seat == 1 and table.model.view().player == 1, "native perspective follows the actual human"):
		return
	for ref in table.model.view().get("private", {}).get("hand", []):
		if not check(not str(ref).begins_with("player:3:"), "the other player's cards never render"):
			return
	var deadline = Time.get_ticks_msec() + 5000
	while not table.doorbell.live and Time.get_ticks_msec() < deadline:
		await process_frame
	if not check(table.doorbell.live, "SSE connection established"):
		return
	if mode == "open":
		var switched = false
		for attempt in range(45):
			if table.model.active_seat == 3:
				switched = true
				break
			if table.model.summary().get("confirmation") == table.model.active_seat:
				table.finish_button.pressed.emit()
				await wait_ready()
			elif not await play_first():
				return
		if not check(switched and table.model.view().player == 3, "local table follows hotseat handover"):
			return
	else:
		var released = await host.call_json(HTTPClient.METHOD_POST, "/games/" + game + "/seats/1/release")
		if not check(released.ok, "host releases a claimed seat"):
			return
		deadline = Time.get_ticks_msec() + 5000
		while table.model.active_seat >= 0 and Time.get_ticks_msec() < deadline:
			await process_frame
		if not check(table.model.active_seat == -1 and table.model.view().is_empty() and table.hand.get_child_count() == 0, "SSE release clears private cards and controls"):
			return
		if not check(not await table._send_action({"index": 0}), "a released seat cannot send a move"):
			return
	# Finished AI-only games expose review views, never live choice controls.
	var finished = await host.call_json(HTTPClient.METHOD_POST, "/games", {"seats": ["random", "random", "random", "random"], "game_seed": 11, "ai_pace": "instant"})
	if not check(finished.ok and finished.data.finished, "AI-only game finishes"):
		return
	await table._adopt_game(str(finished.data.game_id))
	table.tools_ui.playback = false
	if not check(not table.tools_ui.review.is_empty() and table.finish_button.disabled, "AI-only game opens readonly review"):
		return
	if not await table.tools_ui.review_goto(3):
		check(false, "review cursor")
		return
	if not check(int(table.tools_ui.review.cursor) == 3 and table.model.actions().is_empty(), "review seeks without exposing live actions"):
		return
	if not await table.tools_ui._review_meta(2, 3):
		check(false, "review perspective")
		return
	if not check(table.model.active_seat == 2 and int(table.tools_ui.review.cursor) == 3, "review switches seat at the same step"):
		return
	var live = await host.call_json(HTTPClient.METHOD_GET, "/games/" + str(finished.data.game_id))
	if not check(live.data.revision == finished.data.revision, "seeking never mutates the finished game"):
		return
	var saved = await host.call_json(HTTPClient.METHOD_POST, "/games/" + str(finished.data.game_id) + "/save", {"name": "네이티브 계약 검사"})
	if not check(saved.ok, "named save"):
		return
	var loaded = await host.call_json(HTTPClient.METHOD_POST, "/saves/" + str(saved.data.save_id) + "/load")
	if not check(loaded.ok and loaded.data.finished and loaded.data.game_id != finished.data.game_id, "restore uses a new game identity"):
		return
	print("GODOT_CONTRACTS_OK ", JSON.stringify({"mode": mode, "checks": checks}))
	timer.stop()
	await table._quit_cleanly()
