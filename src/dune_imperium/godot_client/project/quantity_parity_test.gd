extends "res://parity_test.gd"


func amount_control(id: String) -> OptionButton:
	for select in table.content.find_children("*", "OptionButton", true, false):
		var family = select.get_meta("quantity_actions", [])
		if not family.is_empty() and family[0].action_id == id:
			return select
	return null


func run() -> void:
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 150
	timer.timeout.connect(func(): push_error("GODOT_PARITY_TIMEOUT"); quit(1))
	root.add_child(timer)
	timer.start()
	table = load("res://main.tscn").instantiate()
	table.tools_ui.prefs_file = directory + "/quantity-ui.json"
	table.api.cookie_file = directory + "/quantity-cookies.json"
	root.add_child(table)
	while table.model.catalog.is_empty() or table.tools_ui.table == null:
		await process_frame
	table.tools_ui.prefs.clear()
	table.tools_ui.prefs.animations = false
	table.tools_ui.prefs.sounds = false
	for scenario in scenarios:
		if not check(await table._adopt_game(str(scenario.game)), "adopt amount position"):
			continue
		await settled()
		table.model.language = str(scenario.language)
		table._render()
		var revision = int(table.model.summary().revision)
		var select = amount_control(str(scenario.action_id))
		if not check(select != null, "all count families, including zero-only auctions, have a quantity control"):
			continue
		var expected = scenario.indices.map(func(index): return int(index))
		check(select.get_meta("action_indices") == expected, "native amounts contain exactly the browser's legal DTO indices")
		check(int(select.get_meta("quantity_actions")[select.selected].index) == int(scenario.default_index), "the default quantity equals the browser's")
		check(select.disabled == (expected.size() == 1), "a fixed single amount cannot be changed")
		var position = expected.find(int(scenario.index))
		select.select(position)
		select.item_selected.emit(position)
		await settled()
		var live = await table.api.call_json(HTTPClient.METHOD_GET, "/games/" + table.game_id + "/snapshot?seat=" + str(int(scenario.seat)))
		check(live.ok and int(live.data.summary.revision) == revision and table.model.held_action().is_empty(), "setting an amount makes no request and does not auto-hold a choice")
		select = amount_control(str(scenario.action_id))
		if not check(select != null and int(select.get_meta("quantity_actions")[select.selected].index) == int(scenario.index), "the selected amount survives a native redraw"):
			continue
		await capture_evidence("amount-" + str(scenario.action_id) + "-" + str(scenario.count) + "-" + str(scenario.language))
		if scenario.auction:
			var submit = table.content.find_children("*", "Button", true, false).filter(func(button): return button.has_meta("quantity_select") and button.get_meta("quantity_select") == select)
			check(submit.is_empty(), "an auction has no separate send button")
			check(not table.finish_button.disabled and table.finish_button.text == scenario.finish_label, "one enabled turn-end control names the staged amount and currency")
			await table._finish()
		else:
			var submit = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == int(scenario.index))
			if not check(submit.size() == 1, "the ordinary quantity has one explicit choice button"):
				continue
			submit[0].pressed.emit()
			await settled()
			if not table.model.held_action().is_empty():
				await table._finish()
		await settled()
		check(int(table.model.summary().revision) == revision + int(scenario.steps), "turn end sends the same number of engine steps as the browser")
	if failed:
		quit(1)
		return
	print("GODOT_PARITY_OK %d" % checks)
	await table._quit_cleanly()
