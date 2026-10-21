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
	table.tools_ui.prefs_file = "res://../../../../tmp/godot/contracts/" + mode + "-ui.json"
	table.api.cookie_file = "res://../../../../tmp/godot/contracts/" + mode + "-native-cookies.json"
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
	# Whole placements stand for an Agent turn's card and space picks.
	var action = table.model.table_actions()[0]
	var before = table.model.signature()
	if action.action_id == "agent_turn":
		await table._choose_ref(action.arguments.card_id)
		await table._choose_ref(action.arguments.space_id)
		if table.model.signature() != before:
			return true
	else:
		for select in table.content.find_children("*", "OptionButton", true, false):
			var offered = select.get_meta("action_indices", [])
			if int(action.index) in offered:
				var position = offered.find(int(action.index))
				select.select(position)
				select.item_selected.emit(position)
				break
	await process_frame
	if action.action_id in table.Model.END_ACTIONS or action.action_id in table.Model.AUCTION_AMOUNTS:
		table.finish_button.pressed.emit()
	else:
		var found = false
		for button in action_buttons(table.content):
			if int(button.get_meta("action_index")) == int(action.index) and (action.get("placement") == null or int(button.get_meta("placement", -1)) == int(action.placement)):
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
	if mode == "remote":
		if not check(table.model.server_info.admin, "one-use host credentials authenticate the native window"):
			return
	table.api.cookies.entries = peer.cookies.entries.duplicate(true)
	if not await table._adopt_game(game):
		check(false, "native game adopt")
		return
	await wait_ready()
	if not check(table.model.active_seat == 1 and table.model.view().player == 1, "native perspective follows the actual human"):
		return
	var owner_badges = table.seats.find_children("*", "Label", true, false).filter(func(label): return label.get_meta("seat_view", "") == "owned")
	if not check(owner_badges.size() == 1, "local hotseat and remote claims identify only this session's current own seat"):
		return
	for ref in table.model.view().get("private", {}).get("hand", []):
		if not check(not str(ref).begins_with("player:3:"), "the other player's cards never render"):
			return
	var deadline = Time.get_ticks_msec() + 5000
	while not table.doorbell.live and Time.get_ticks_msec() < deadline:
		await process_frame
	if not check(table.doorbell.live, "SSE connection established"):
		return
	table.doorbell._retry()
	deadline = Time.get_ticks_msec() + 6000
	while not table.doorbell.live and Time.get_ticks_msec() < deadline:
		await process_frame
	if not check(table.doorbell.live, "SSE reconnects after a dropped stream"):
		return
	var original_hand = table.model.view().private.hand.duplicate()
	if original_hand.size() >= 2:
		var revision = table.model.summary().revision
		table.layout_ui.move(original_hand[-1], original_hand[0], "hand")
		if not check(table.layout_ui.ordered(original_hand, "hand")[0] == original_hand[-1] and table.model.view().private.hand == original_hand and table.model.summary().revision == revision, "local card order never changes engine hand order or revision"):
			return
	table.model.language = "en"
	table._render()
	if not check(table.new_button.text == "New Game" and table.own_line.text.begins_with("My hand"), "English updates existing chrome and dynamic hand labels"):
		return
	table.model.language = "ko"
	table._render()
	var pile = table._open_pile("Private hand test", original_hand, true)
	var viewer = pile.get_meta("pile_viewer")
	viewer.inspect(str(original_hand[0]))
	if not check(viewer.heading.text == table.model.name_of(str(original_hand[0])) and viewer.refs.size() == original_hand.size() and not viewer.preserve_order, "live pile viewer reads its card and cannot expose hidden order"):
		return
	pile.confirmed.emit()
	await process_frame
	if mode == "open":
		var original = table.model.view().private.hand.duplicate()
		if not await play_first():
			return
		pile = table._open_pile("Hand across undo", table.model.view().private.hand)
		viewer = pile.get_meta("pile_viewer")
		table._open_details(str(original[0]))
		var detail = table.find_children("*", "Window", true, false).filter(func(window): return window.has_meta("detail_ref"))[0]
		if not check(await table._mutate("undo", {"steps": table.model.undo_steps()}), "undo while a pile and nested detail are open"):
			return
		if not check(viewer.refs == original and pile.visible and (not is_instance_valid(detail) or not detail.visible), "undo refreshes the pile and closes its stale nested detail"):
			return
		pile.confirmed.emit()
		await process_frame
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
		var outer = AcceptDialog.new()
		outer.exclusive = true
		table.add_child(outer)
		outer.popup_centered(Vector2i(200, 100))
		table._open_details(str(original_hand[0]))
		var detail = table.find_children("*", "Window", true, false).filter(func(window): return window.has_meta("detail_ref"))[0]
		var released = await host.call_json(HTTPClient.METHOD_POST, "/games/" + game + "/seats/1/release")
		if not check(released.ok, "host releases a claimed seat"):
			return
		deadline = Time.get_ticks_msec() + 5000
		while table.model.active_seat >= 0 and Time.get_ticks_msec() < deadline:
			await process_frame
		if not check(table.model.active_seat == -1 and table.model.view().is_empty() and table.hand.get_child_count() == 0, "SSE release clears private cards and controls"):
			return
		if not check(not is_instance_valid(detail) or not detail.visible, "seat loss closes a private detail nested under an untagged window"):
			return
		outer.hide()
		outer.queue_free()
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
	if not check(table.turn_label.get_meta("turn_kind") == "review" and table.seats.get_children().all(func(panel): return not panel.get_meta("seat_current", false)), "a review never highlights the retained live summary's owner or finished state"):
		return
	var review_badges = table.seats.find_children("*", "Label", true, false).filter(func(label): return label.has_meta("seat_view"))
	if not check(review_badges.size() == 1 and review_badges[0].get_meta("seat_view") == "viewing", "an AI-only review names a viewed seat without claiming it"):
		return
	var first_badges = table.seats.find_children("*", "Label", true, false).filter(func(label): return label.has_meta("seat_first"))
	if not check(first_badges.size() == 1 and int(first_badges[0].get_meta("seat_first")) == int(table.model.view().first_player), "review's first-player badge uses the historical public view"):
		return
	pile = table._open_pile("Review private hand", table.model.view().get("private", {}).get("hand", []))
	table._open_details(str(table.model.view().players[table.model.active_seat].leader_id))
	var private_detail = table.find_children("*", "Window", true, false).filter(func(window): return window.has_meta("detail_ref"))[0]
	if not await table.tools_ui._review_meta(2, 3):
		check(false, "review perspective")
		return
	if not check(table.model.active_seat == 2 and int(table.tools_ui.review.cursor) == 3, "review switches seat at the same step"):
		return
	if not check((not is_instance_valid(pile) or not pile.visible) and (not is_instance_valid(private_detail) or not private_detail.visible), "review perspective changes close private piles and nested details"):
		return
	pile = table._open_pile("Review pile before seek", table.model.view().get("private", {}).get("hand", []))
	await table.tools_ui.review_goto(4)
	if not check(not is_instance_valid(pile) or not pile.visible, "review cursor changes close information from the previous position"):
		return
	await table.tools_ui.review_goto(3)
	table.tools_ui.playback_interval = 0.05
	table.tools_ui.playback_unit = "step"
	table.tools_ui.playback = true
	table.tools_ui._playback_next()
	deadline = Time.get_ticks_msec() + 3000
	while int(table.tools_ui.review.cursor) == 3 and Time.get_ticks_msec() < deadline:
		await process_frame
	table.tools_ui.playback = false
	if not check(int(table.tools_ui.review.cursor) > 3 and table.finish_button.disabled, "review playback advances without enabling live moves"):
		return
	var slider: HSlider
	for control in table.content.find_children("*", "HSlider", true, false):
		if control.has_meta("review_slider"):
			slider = control
	slider.value = 8
	deadline = Time.get_ticks_msec() + 3000
	while int(table.tools_ui.review.cursor) != 8 and Time.get_ticks_msec() < deadline:
		await process_frame
	if not check(int(table.tools_ui.review.cursor) == 8, "keyboard/value changes seek the review slider without a mouse drag"):
		return
	var deck = table.model.view().disclosure.imperium_deck
	pile = table._open_pile("Disclosed deck order", deck, true)
	viewer = pile.get_meta("pile_viewer")
	if not check(viewer.preserve_order and viewer.shown.map(func(group): return group.ref) == deck, "ended-game disclosure keeps each physical card in server deck order"):
		return
	pile.confirmed.emit()
	await process_frame
	var live = await host.call_json(HTTPClient.METHOD_GET, "/games/" + str(finished.data.game_id))
	if not check(live.data.revision == finished.data.revision, "seeking never mutates the finished game"):
		return
	var saved = await host.call_json(HTTPClient.METHOD_POST, "/games/" + str(finished.data.game_id) + "/save", {"name": "네이티브 계약 검사"})
	if not check(saved.ok, "named save"):
		return
	var loaded = await host.call_json(HTTPClient.METHOD_POST, "/saves/" + str(saved.data.save_id) + "/load")
	if not check(loaded.ok and loaded.data.finished and loaded.data.game_id != finished.data.game_id, "restore uses a new game identity"):
		return
	# All destructive UI checks use only the dedicated test server/save directory.
	table.api.cookies.entries = host.cookies.entries.duplicate(true)
	if mode == "remote":
		table.model.server_info.admin = true
	var save_dialog = await table._show_saves()
	var remove: Button
	for button in save_dialog.find_children("*", "Button", true, false):
		if button.get_meta("delete_save_id", "") == str(saved.data.save_id):
			remove = button
	if not check(remove != null, "save has a deletion control"):
		return
	remove.pressed.emit()
	var confirmation: ConfirmationDialog
	for child in table.find_children("*", "Window", true, false):
		if child is ConfirmationDialog:
			confirmation = child
	if not check(confirmation != null, "save deletion asks for a second explicit click"):
		return
	confirmation.canceled.emit()
	await process_frame
	var list = await host.call_json(HTTPClient.METHOD_GET, "/saves")
	if not check(list.data.any(func(row): return str(row.save_id) == str(saved.data.save_id)), "cancel preserves the saved game"):
		return
	remove.pressed.emit()
	for child in table.find_children("*", "Window", true, false):
		if child is ConfirmationDialog and not child.is_queued_for_deletion():
			confirmation = child
	confirmation.confirmed.emit()
	await create_timer(0.2).timeout
	list = await host.call_json(HTTPClient.METHOD_GET, "/saves")
	if not check(not list.data.any(func(row): return str(row.save_id) == str(saved.data.save_id)), "confirmed deletion removes only the selected test save"):
		return
	var fake_list = AcceptDialog.new()
	table.add_child(fake_list)
	table.tools_ui.delete_game(str(loaded.data.game_id), fake_list)
	for child in table.find_children("*", "Window", true, false):
		if child is ConfirmationDialog and child.has_meta("delete_game_id"):
			confirmation = child
	confirmation.canceled.emit()
	var kept = await host.call_json(HTTPClient.METHOD_GET, "/games/" + str(loaded.data.game_id))
	if not check(kept.ok, "cancel preserves the selected game"):
		return
	table.tools_ui.delete_game(str(loaded.data.game_id), fake_list)
	for child in table.find_children("*", "Window", true, false):
		if child is ConfirmationDialog and child.has_meta("delete_game_id") and not child.is_queued_for_deletion():
			confirmation = child
	confirmation.confirmed.emit()
	await create_timer(0.2).timeout
	kept = await host.call_json(HTTPClient.METHOD_GET, "/games/" + str(loaded.data.game_id))
	if not check(not kept.ok, "confirmed deletion removes the selected test game"):
		return
	print("GODOT_CONTRACTS_OK ", JSON.stringify({"mode": mode, "checks": checks}))
	timer.stop()
	await table._quit_cleanly()
