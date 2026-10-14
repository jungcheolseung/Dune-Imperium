extends SceneTree

# These expectations come from the actual browser at the same saved position.
# The Python runner compares both clients' resulting authorized snapshots.
var table: Control
var checks = 0
var failed = false
var scenarios: Array = []
var directory = ""


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--scenarios="):
			var path = argument.trim_prefix("--scenarios=")
			directory = path.get_base_dir()
			scenarios = JSON.parse_string(FileAccess.get_file_as_string(path))
	call_deferred("run")


func check(condition: bool, message: String) -> bool:
	checks += 1
	if not condition:
		failed = true
		push_error("GODOT_PARITY_FAILED: " + message)
	return condition


func settled() -> void:
	while table.busy or table.refreshing:
		await process_frame
	await process_frame


func indices(rows: Array) -> Array:
	var result = rows.map(func(action): return int(action.index))
	result.sort()
	return result


func run() -> void:
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 120
	timer.timeout.connect(func(): push_error("GODOT_PARITY_TIMEOUT"); quit(1))
	root.add_child(timer)
	timer.start()
	table = load("res://main.tscn").instantiate()
	table.tools_ui.prefs_file = directory + "/native-ui.json"
	table.api.cookie_file = directory + "/native-cookies.json"
	root.add_child(table)
	while table.model.catalog.is_empty() or table.tools_ui.table == null:
		await process_frame
	table.tools_ui.prefs.clear()
	table.tools_ui.prefs.animations = false
	table.tools_ui.prefs.sounds = false
	for scenario in scenarios:
		if not await table._adopt_game(str(scenario.game)):
			check(false, "adopt " + str(scenario.kind))
			continue
		await settled()
		var revision = int(table.model.summary().revision)
		if scenario.kind == "held":
			await table._choose_ref(str(scenario.card))
			check(int(table.model.held_action().get("index", -1)) == int(scenario.index), "table holds the browser's exact choice")
			await table._choose_ref(str(scenario.card))
			check(int(table.model.held_action().get("index", -1)) == int(scenario.index), "second table click keeps the choice held")
			check(int(table.model.summary().revision) == revision, "holding sends no action")
			if table.model.has_method("picked_ref"):
				check(table.model.picked_ref(str(scenario.card)), "held table card is highlighted")
			var action = table.model.actions().filter(func(row): return int(row.index) == int(scenario.index))[0]
			await table._choose_action(action, table.model.signature())
			check(table.model.held_action().is_empty(), "list row cancels the held choice")
			await table._choose_ref(str(scenario.card))
			await table._finish()
		else:
			if scenario.kind == "unique" and not scenario.get("space_first", false) and table.has_method("_apply_placement"):
				var toggles = table.content.find_children("*", "Button", true, false).filter(func(button): return button.has_meta("action_list_toggle"))
				toggles[0].pressed.emit()
				var listed: Array = []
				var expected = indices(table.model.placements())
				for button in table.content.find_children("*", "Button", true, false):
					var index = int(button.get_meta("action_index", -1))
					if index in expected:
						listed.append(index)
				listed.sort()
				check(listed == expected, "the full-list toggle reaches every placement DTO")
				toggles = table.content.find_children("*", "Button", true, false).filter(func(button): return button.has_meta("action_list_toggle"))
				toggles[0].pressed.emit()
				check(not table.tools_ui.prefs.full_action_list and int(table.model.summary().revision) == revision, "returning to staged picks makes no engine move")
			# Card-first and space-first must project the same legal choices.
			var first = str(scenario.space) if scenario.get("space_first", false) else str(scenario.card)
			var second = str(scenario.card) if scenario.get("space_first", false) else str(scenario.space)
			await table._choose_ref(first)
			check(int(table.model.summary().revision) == revision, "first pick makes no request")
			var lit: Array = []
			for ref in table.model.legal_refs():
				var relevant = ref in table.model.view().private.hand if scenario.get("space_first", false) else table.model.catalog.spaces.has(ref)
				if relevant:
					lit.append(ref)
			lit.sort()
			check(lit == scenario.lit, "browser and native light the same objects")
			if scenario.has("partner"):
				await table._choose_ref(str(scenario.partner))
				check(str(table.model.get("selected_partner")) == str(scenario.partner), "the second hand card joins the pair")
			await table._choose_ref(second)
			await settled()
			if scenario.kind == "multiple":
				check(int(table.model.summary().revision) == revision, "ambiguous placement waits for its option")
				var expected_indices = scenario.candidates.map(func(index): return int(index))
				var shown: Array = []
				for button in table.content.find_children("*", "Button", true, false):
					var index = int(button.get_meta("action_index", -1))
					if index in expected_indices:
						shown.append(index)
				shown.sort()
				check(shown == expected_indices, "native chooser contains exactly the browser options")
				for expected in scenario.costs:
					var action = table.model.actions().filter(func(row): return int(row.index) == int(expected.index))[0]
					check(table.model.paid_cost(action) == expected.paid, "displayed cost equals browser's paid cost")
					if action.arguments.has("discount"):
						var paid = table.model.cost_text(table.model.paid_cost(action))
						check(table.model.describe(action).contains(table.model.native("지불 비용: ") + (table.model.ui("render.free") if paid.is_empty() else paid)), "the actual action label names the discounted payment")
				var chosen = table.model.actions().filter(func(row): return int(row.index) == int(scenario.index))[0]
				if table.has_method("_apply_placement"):
					await table._apply_placement(chosen, table.model.signature())
				else:
					await table._choose_action(chosen, table.model.signature())
			else:
				check(int(table.model.summary().revision) == revision + int(scenario.steps), "a complete unique pick applies without an extra click")
		await settled()
		check(int(table.model.summary().revision) == revision + int(scenario.steps), "expected actions reached the engine")
		if scenario.has("partner"):
			check(table.model.summary().get("decision", {}).get("kind") != "graft_partner", "the selected graft partner follows once")
	if failed:
		quit(1)
		return
	print("GODOT_PARITY_OK %d" % checks)
	await table._quit_cleanly()
