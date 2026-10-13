extends Node

# Exercise the player's controls, including held choices and Turn End.
# Only this developer runner chooses automatically; normal play never does.
var table: Control
var report: Dictionary = {"games": [], "actions": {}, "decisions": {}, "phases": {}, "held_choices": 0, "confirmations": 0, "restores": 0}
var rng = RandomNumberGenerator.new()
var stopped = false


func fail(message: String) -> void:
	stopped = true
	table._smoke_fail("playthrough: " + message)


func ready_frame() -> void:
	while true:
		await get_tree().process_frame
		if not table.busy and not table.refreshing:
			break


func count_key(group: String, key: String) -> void:
	report[group][key] = int(report[group].get(key, 0)) + 1


func buttons(node: Node) -> Array[Button]:
	var result: Array[Button] = []
	for child in node.get_children():
		if child is Button:
			result.append(child)
		result.append_array(buttons(child))
	return result


func press_action(action: Dictionary) -> void:
	if action.action_id == "agent_turn":
		table._choose_ref(action.arguments.card_id)
		table._choose_ref(action.arguments.space_id)
	else:
		table._set_tab("choices")
	await get_tree().process_frame
	if action.action_id in table.Model.END_ACTIONS:
		if table.finish_button.disabled:
			fail("finish control disabled: " + str(action.action_id))
			return
		table.finish_button.pressed.emit()
	else:
		var found = false
		for button in buttons(table.content):
			if int(button.get_meta("action_index", -1)) == int(action.index):
				if button.disabled or button.text.is_empty():
					fail("action control disabled or empty")
					return
				button.pressed.emit()
				found = true
				break
		if not found:
			fail("missing action control: " + JSON.stringify(action))
			return
		if action.get("sent_by_turn_end", false):
			if table.model.held_action().is_empty() or table.finish_button.disabled:
				fail("choice cannot be confirmed")
				return
			report.held_choices += 1
			table.finish_button.pressed.emit()
	if not table.busy or not table.new_button.disabled or not table.undo_button.disabled or not table.finish_button.disabled:
		fail("inputs unlocked before action and snapshot complete")
		return
	await ready_frame()


func check_choices() -> bool:
	table._set_tab("choices")
	var offered: Dictionary = {}
	for button in buttons(table.content):
		var index = int(button.get_meta("action_index", -1))
		if index >= 0:
			offered[index] = true
	for action in table.model.actions():
		if action.action_id == "agent_turn":
			if table.model.placements(action.arguments.card_id, action.arguments.space_id).is_empty():
				return false
		elif action.action_id in table.Model.END_ACTIONS:
			if int(table.model.finish_action().get("index", -1)) != int(action.index):
				return false
		elif not offered.has(int(action.index)):
			return false
	return true


func pick_action(actions: Array) -> Dictionary:
	var chosen: Dictionary = {}
	var best = -INF
	for action in actions:
		var score = rng.randf()
		# Sample more kinds of real effects, with occasional early Reveal/pass.
		if not report.actions.has(str(action.action_id)):
			score += 0.7
		if str(action.action_id).begins_with("acquire_"):
			score += 0.4
		if action.action_id == "agent_turn":
			score += 0.4
		if score > best:
			best = score
			chosen = action
	return chosen


func restore_midgame() -> void:
	var summary = table.model.summary().duplicate(true)
	var view = table.model.view().duplicate(true)
	var reply = await table._save_game()
	if not reply.get("ok", false):
		fail("save")
		return
	var save_id = str(reply.data.save_id)
	var dialog = await table._show_saves()
	if dialog == null:
		fail("saved games dialog")
		return
	if not table.capture_dir.is_empty():
		await table._capture("saves")
	var found = false
	for button in buttons(dialog):
		if button.get_meta("save_id", "") == save_id:
			button.pressed.emit()
			found = true
			break
	if not found:
		fail("saved game absent from list")
		return
	await ready_frame()
	var restored = table.model.summary()
	if str(restored.game_id) == str(summary.game_id) or int(restored.revision) != int(summary.revision) or restored.get("confirmation") != summary.get("confirmation") or table.model.view() != view:
		fail("restored state differs from saved state")
		return
	report.restores += 1


func run(client: Control, seeds: String) -> void:
	table = client
	Engine.max_fps = 240
	var watchdog = Timer.new()
	watchdog.wait_time = 600
	watchdog.one_shot = true
	watchdog.timeout.connect(func(): fail("timeout"))
	add_child(watchdog)
	watchdog.start()
	var game_index = 0
	for value in seeds.split(",", false):
		var seed_value = int(value)
		rng.seed = seed_value
		var draft = game_index % 2 == 1
		# Skip presentation delays in the bounded test, retaining the same AI.
		if not await table._create_game(seed_value, draft, "instant"):
			fail("create")
			return
		var restored = false
		var captured_combat = false
		var steps = 0
		var deadline = Time.get_ticks_msec() + 240000
		var last_round = -1
		while not table.model.summary().get("finished", false):
			if stopped:
				return
			if steps >= 1700 or Time.get_ticks_msec() > deadline:
				fail("game did not finish, seed=" + value)
				return
			var summary = table.model.summary()
			if int(summary.round_number) != last_round:
				last_round = int(summary.round_number)
				print("GODOT_PLAYTHROUGH_ROUND seed=", seed_value, " round=", last_round)
			count_key("phases", str(summary.phase))
			if summary.get("thinking") != null:
				await get_tree().create_timer(0.02).timeout
				await table._sync()
				continue
			if not captured_combat and str(summary.phase) == "combat" and not table.capture_dir.is_empty():
				await table._capture("combat")
				captured_combat = true
			if not restored and int(summary.round_number) >= 2:
				await restore_midgame()
				if stopped:
					return
				restored = true
				continue
			if summary.get("confirmation") == 0:
				if table.finish_button.disabled:
					fail("confirmation control disabled")
					return
				table.finish_button.pressed.emit()
				await ready_frame()
				report.confirmations += 1
			else:
				var actions = table.model.actions()
				if actions.is_empty():
					fail("no available action: " + JSON.stringify(summary))
					return
				# Every offered choice must be reachable, including those not picked.
				if not check_choices():
					fail("legal action omitted from the choice controls")
					return
				count_key("decisions", str(summary.get("decision", {}).get("kind", "")))
				var action = pick_action(actions)
				var before = table.model.signature()
				await press_action(action)
				if stopped:
					return
				if before == table.model.signature():
					fail("action did not advance: " + JSON.stringify(action))
					return
				count_key("actions", str(action.action_id))
			steps += 1
		var final = table.model.summary()
		if not restored or final.get("standings", []).size() != 4 or not table.finish_button.disabled:
			fail("missing restore, final standings or disabled finish")
			return
		table._set_tab("choices")
		var text = ""
		for label_node in table.content.get_children():
			if label_node is Label:
				text += label_node.text
		if not text.contains("최종 순위"):
			fail("missing result screen")
			return
		if not table.capture_dir.is_empty():
			await table._capture("results")
		report.games.append({"seed": seed_value, "draft": draft, "round": final.round_number, "revision": final.revision, "steps": steps, "leader": table.model.view().players[0].leader_id, "standings": final.standings})
		print("GODOT_GAME_FINISHED ", JSON.stringify(report.games[-1]))
		game_index += 1
	watchdog.stop()
	print("GODOT_PLAYTHROUGH_OK ", JSON.stringify(report))
	table.smoke_done = true
	await table._quit_cleanly()
