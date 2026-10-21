extends "res://parity_test.gd"


func compare_layout(expected: Dictionary, phase: String) -> void:
	var boxes: Array = []
	var locks: Array = []
	var zones: Array = []
	for label in table.content.find_children("*", "Label", true, false):
		if label.has_meta("agent_box"):
			boxes.append({"box": int(label.get_meta("agent_box")), "text": label.text})
		if label.has_meta("locked_box"):
			locks.append({"box": int(label.get_meta("locked_box")), "text": label.text})
		if label.has_meta("choice_zone"):
			zones.append({"zone": label.get_meta("choice_zone"), "text": label.text})
	var expected_boxes = expected.boxes.map(func(box): return {"box": int(box.box), "text": box.text})
	var expected_locks = expected.locks.map(func(box): return {"box": int(box.box), "text": box.text})
	if not check(boxes == expected_boxes, phase + ": real browser box headings and order"):
		print("BOX_DIFFERENCE ", JSON.stringify([boxes, expected_boxes]))
	check(locks == expected_locks, phase + ": real browser locked-box notes")
	check(JSON.stringify(zones) == JSON.stringify(expected.zones), phase + ": real browser pile headings and counts")
	var found: Array = []
	for button in table.content.find_children("*", "Button", true, false):
		if button.has_meta("action_index"):
			found.append(int(button.get_meta("action_index")))
	var want = expected.indices.map(func(index): return int(index))
	if not check(found == want, phase + ": every visible browser action appears once in the same order"):
		print("ACTION_DIFFERENCE ", JSON.stringify([found, want]))
	for suffix in expected.suffixes:
		var buttons = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == int(suffix.index))
		if not buttons.is_empty():
			var words = buttons[0].find_children("*", "Label", true, false).map(func(label): return label.text)
			check(buttons[0].get_meta("choice_suffix", "") == suffix.text and words.any(func(text): return str(text).ends_with(suffix.text)), phase + ": physical copy/current turn/lost-box warning matches the browser")


func press_action(index: int) -> void:
	var buttons = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == index)
	if check(buttons.size() == 1 and not buttons[0].disabled, "the chosen legal row is reachable"):
		buttons[0].pressed.emit()
		await settled()


func key(code: int, modified = false) -> void:
	var event = InputEventKey.new()
	event.physical_keycode = code
	event.pressed = true
	event.ctrl_pressed = modified
	Input.parse_input_event(event)
	await process_frame
	await process_frame
	event = event.duplicate()
	event.pressed = false
	Input.parse_input_event(event)
	await process_frame


func inspect_and_shortcuts(scenario: Dictionary) -> void:
	print("CHOICE_INSPECT_START ", scenario.kind, " ", scenario.language)
	var revision = int(table.model.summary().revision)
	var details = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_detail_index", -1)) == int(scenario.index))
	if not check(details.size() == 1, "the selected effect has a detail control"):
		return
	details[0].pressed.emit()
	print("CHOICE_DETAIL_OPENED")
	await settled()
	var dialogs = table.find_children("*", "Window", true, false).filter(func(window): return window.visible and not window.is_queued_for_deletion() and window.has_meta("action_detail_index"))
	if not check(dialogs.size() == 1, "effect detail opens an information window"):
		return
	var dialog = dialogs[0]
	print("CHOICE_DETAIL_SIZE ", dialog.size)
	var shown: Array = []
	for label in dialog.find_children("*", "Label", true, false):
		if label.has_meta("action_preview_ref"):
			shown.append(label.text)
	check(scenario.previews.all(func(name): return name in shown), "every card/space preview shown by the real browser is also inspectable")
	var folded = table.tools_ui.prefs.get("market_folded", false)
	await key(KEY_C)
	check(table.tools_ui.prefs.get("market_folded", false) == folded, "an information window owns the keyboard and does not fold the table behind it")
	if scenario.kind != "trash-earlier":
		await capture_evidence("effect-detail-" + str(scenario.fixture) + "-" + str(scenario.language))
	dialog.confirmed.emit()
	await process_frame
	var focus = table.get_viewport().gui_get_focus_owner()
	if focus != null:
		focus.release_focus()
	await key(KEY_C)
	check(table.tools_ui.prefs.market_folded != folded and table.market_scroll.get_parent().visible == folded, "physical C folds the shared market without losing its state")
	await key(KEY_C, true)
	check(table.tools_ui.prefs.market_folded != folded, "Ctrl shortcuts are left to their owner")
	await key(KEY_C)
	check(table.tools_ui.prefs.market_folded == folded, "physical C restores the market")
	var typing = LineEdit.new()
	table.add_child(typing)
	typing.grab_focus()
	await key(KEY_C)
	check(table.tools_ui.prefs.market_folded == folded, "typing a name cannot fold the table")
	typing.release_focus()
	typing.queue_free()
	var expanded = table.tools_ui.prefs.get("seat_details", false)
	await key(KEY_S)
	check(table.tools_ui.prefs.seat_details != expanded, "physical S expands seat details")
	await key(KEY_S)
	check(table.tools_ui.prefs.seat_details == expanded, "physical S restores seat details")
	check(int(table.model.summary().revision) == revision, "inspection and keyboard folding leave the engine unchanged")


func run() -> void:
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 240
	timer.timeout.connect(func(): push_error("GODOT_PARITY_TIMEOUT"); quit(1))
	root.add_child(timer)
	timer.start()
	table = load("res://main.tscn").instantiate()
	table.tools_ui.prefs_file = directory + "/choice-ui.json"
	table.api.cookie_file = directory + "/choice-cookies.json"
	root.add_child(table)
	while table.model.catalog.is_empty() or table.tools_ui.table == null:
		await process_frame
	table.tools_ui.prefs.clear()
	table.tools_ui.prefs.animations = false
	table.tools_ui.prefs.sounds = false
	for scenario in scenarios:
		if not check(await table._adopt_game(str(scenario.game)), "adopt real choice position"):
			continue
		await settled()
		table.model.language = str(scenario.language)
		table._render()
		var seat = table.model.active_seat
		compare_layout(scenario.before, "before")
		await inspect_and_shortcuts(scenario)
		if scenario.kind != "trash-earlier":
			await capture_evidence(str(scenario.fixture) + "-" + str(scenario.language))
		var revision = int(table.model.summary().revision)
		await press_action(int(scenario.index))
		check(int(table.model.summary().revision) == revision + 1, "one click sends only the offered step")
		check_receipt(seat)
		compare_layout(scenario.after, "after")
		if scenario.kind == "box":
			await capture_evidence("box-locked-" + str(scenario.language))
			await table._mutate("undo", {"steps": 1})
			compare_layout(scenario.restored, "undo")
			check(int(table.model.summary().undo_count) == 1, "undo creates a fresh action generation")
			check(not table.feedback.visible and table.feedback.receipt.is_empty(), "undo clears the previous applied receipt")
			await press_action(int(scenario.other_index))
			check(int(table.model.summary().revision) == revision + 1, "the second card's effect applies without a switch step")
	if failed:
		quit(1)
		return
	print("GODOT_PARITY_OK %d" % checks)
	await table._quit_cleanly()
