extends "res://parity_test.gd"


func run() -> void:
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 120
	timer.timeout.connect(func(): push_error("GODOT_PARITY_TIMEOUT"); quit(1))
	root.add_child(timer)
	timer.start()
	table = load("res://main.tscn").instantiate()
	table.tools_ui.prefs_file = directory + "/info-ui.json"
	table.api.cookie_file = directory + "/info-cookies.json"
	root.add_child(table)
	while table.model.catalog.is_empty() or table.tools_ui.table == null:
		await process_frame
	table.tools_ui.prefs.clear()
	table.tools_ui.prefs.animations = false
	table.tools_ui.prefs.sounds = false
	for scenario in scenarios:
		if not check(await table._adopt_game(str(scenario.game)), "adopt information position"):
			continue
		await settled()
		table.model.language = str(scenario.language)
		table._render()
		var refs = table.model.view().private.deck_cards.duplicate()
		var pile = table._open_pile("Deck", refs)
		var viewer = pile.get_meta("pile_viewer")
		var expected_groups = scenario.groups.map(func(group):
			var entry = group.duplicate()
			entry.count = int(group.count)
			return entry
		)
		if not check(not viewer.preserve_order and viewer.shown == expected_groups, "deck copy groups and Top marker match the actual browser"):
			print("DECK_GROUP_DIFFERENCE ", JSON.stringify([viewer.shown, expected_groups]))
		check(pile.title == scenario.title, "deck title names size and hidden order in both languages")
		if viewer.get("note") != null:
			check(viewer.note.text == scenario.notes[0] and viewer.top_note.text == scenario.notes[1], "deck notes name the authorized information source")
		else:
			check(false, "deck notes are present")
		var hand_refs: Array = []
		for button in table.hand.find_children("*", "Button", true, false):
			if button.has_meta("instance_ref"):
				hand_refs.append(str(button.get_meta("instance_ref")))
		check(str(scenario.top) not in hand_refs, "the private top is not duplicated beside the hand")
		var pictures = table.content.find_children("*", "Button", true, false).filter(func(button): return button.has_meta("deck_top_choice"))
		check(pictures.size() == int(scenario.choice_picture), "Controlled pictures its card only while its choice is offered")
		for expected in scenario.labels:
			var matches = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == int(expected.index))
			if not check(matches.size() == 1 and matches[0].text.split("\n")[0] == expected.text, "the actual private choice button matches the browser label"):
				print("DECK_LABEL_DIFFERENCE ", JSON.stringify([matches[0].text if not matches.is_empty() else "missing", expected.text]))
		pile.confirmed.emit()
		await process_frame
	if failed:
		quit(1)
		return
	print("GODOT_PARITY_OK %d" % checks)
	await table._quit_cleanly()
