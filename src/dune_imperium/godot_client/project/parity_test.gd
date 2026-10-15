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


func reading_lines(button: Button, kind: String) -> Array:
	return button.find_children("*", "Label", true, false).filter(func(label): return label.get_meta("reading_kind", "") == kind)


func check_receipt(seat: int) -> void:
	if table.model.active_seat == seat and seat in table.model.owned_seats:
		if not check(table.feedback.visible and table.feedback.get_meta("feedback_state", "") == "confirmed", "an accepted action with a fresh authorized snapshot shows an applied receipt"):
			return
		var delta = table.feedback.receipt.delta.duplicate()
		table._render()
		check(table.feedback.receipt.delta == delta, "rerendering preserves the already confirmed resource change")
	else:
		check(not table.feedback.visible and table.feedback.receipt.is_empty(), "changing to another seat drops the previous seat's receipt")


func capture_evidence(name: String) -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--evidence="):
			print("PARITY_CAPTURE_START ", name)
			table.capture_dir = argument.trim_prefix("--evidence=")
			DirAccess.make_dir_recursive_absolute(table.capture_dir)
			await table._wait_images()
			print("PARITY_CAPTURE_IMAGES_READY ", name)
			await table._capture(name)
			print("PARITY_CAPTURE_WIDE_READY ", name)
			table.get_window().size = Vector2i(1100, 740)
			await process_frame
			await process_frame
			table._fit_columns()
			for window in table.find_children("*", "Window", true, false):
				if window.visible and not window.is_queued_for_deletion():
					check(Rect2(Vector2.ZERO, table.size).encloses(Rect2(Vector2(window.position), Vector2(window.size))), "open information window remains inside the narrow viewport")
			await table._capture(name + "-narrow")
			table.get_window().size = Vector2i(1440, 900)
			await process_frame
			await process_frame
			table._fit_columns()


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
		var seat = table.model.active_seat
		check(not table.feedback.visible and table.feedback.receipt.is_empty(), "loading a game never replays an old applied receipt")
		if scenario.kind == "unique" and not scenario.get("space_first", false):
			# Feed only response states to the receipt component. The live game
			# snapshot and actions are untouched by these error/unconfirmed checks.
			var context = table.feedback.capture()
			table.feedback.complete(context, table.model.actions()[0], {"ok": false, "data": {"detail": "test response rejected"}})
			check(table.feedback.get_meta("feedback_state") == "rejected" and table.feedback.detail.text == "test response rejected", "a rejected response remains visibly distinct from success")
			table.feedback.complete(context, table.model.actions()[0], {"ok": true})
			check(table.feedback.get_meta("feedback_state") == "unconfirmed" and not table.feedback.receipt.has("delta"), "an accepted response without a new snapshot is not yet an applied receipt")
			check(int(table.model.summary().revision) == revision, "receipt response tests send no engine request")
			table.feedback.reset()
			check(table.feedback.receipt.is_empty() and table.feedback.heading.text.is_empty() and table.feedback.detail.text.is_empty(), "clearing feedback removes cached text as well as its visible state")
		if scenario.kind == "held":
			await table._choose_ref(str(scenario.card))
			check(int(table.model.held_action().get("index", -1)) == int(scenario.index), "table holds the browser's exact choice")
			await table._choose_ref(str(scenario.card))
			check(int(table.model.held_action().get("index", -1)) == int(scenario.index), "second table click keeps the choice held")
			check(int(table.model.summary().revision) == revision, "holding sends no action")
			check(not table.feedback.visible, "a held local choice is not presented as an applied action")
			var held_buttons = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == int(scenario.index))
			if check(held_buttons.size() == 1, "held choice has one visible row"):
				check(reading_lines(held_buttons[0], "held").size() == 1, "held choice explicitly says it still needs turn-end confirmation")
			await capture_evidence("held-choice")
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
					var buttons = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == int(action.index))
					if check(buttons.size() == 1, "each cost option keeps one actual action button"):
						var labels = reading_lines(buttons[0], "payment")
						var paid = table.model.cost_text(expected.paid)
						check(labels.size() == 1 and labels[0].text.begins_with(table.model.native("지불 비용: ") + (paid if not paid.is_empty() else table.model.ui("render.free"))), "the visible payment line starts with the browser's actual cost")
					if action.arguments.has("discount"):
						var paid = table.model.cost_text(table.model.paid_cost(action))
						check(table.model.describe(action).contains(table.model.native("지불 비용: ") + (table.model.ui("render.free") if paid.is_empty() else paid)), "the actual action label names the discounted payment")
				var chosen = table.model.actions().filter(func(row): return int(row.index) == int(scenario.index))[0]
				await capture_evidence("payment-options-ko")
				if Array(OS.get_cmdline_user_args()).any(func(argument): return argument.begins_with("--evidence=")):
					table.model.language = "en"
					table._render()
					await capture_evidence("payment-options-en")
					table.model.language = "ko"
					table._render()
				table._action_details(chosen, str(scenario.card))
				await settled()
				var dialogs = table.find_children("*", "Window", true, false).filter(func(window): return window.visible and not window.is_queued_for_deletion() and window.has_meta("action_detail_index"))
				if check(dialogs.size() == 1, "a placement's two-target preview opens"):
					var labels = dialogs[0].find_children("*", "Label", true, false).map(func(label): return label.text)
					check(scenario.preview_names.all(func(name): return name in labels), "card and board-space preview names equal the actual browser's detail")
					var position = labels.find(table.model.name_of(str(chosen.arguments.space_id)))
					var body = str(labels[position + 1]) if position >= 0 and position + 1 < labels.size() else ""
					check(body.contains(table.model.phrase(scenario.preview_effect)), "the detailed board body contains the browser's selected option, using native amount grammar")
					dialogs[0].confirmed.emit()
					await process_frame
				check(int(table.model.summary().revision) == revision, "inspecting multiple targets never sends a placement")
				var buttons = table.content.find_children("*", "Button", true, false).filter(func(button): return int(button.get_meta("action_index", -1)) == int(chosen.index))
				if check(buttons.size() == 1, "chosen payment surface is reachable"):
					table.content.get_parent().ensure_control_visible(buttons[0])
					await process_frame
					await process_frame
					var labels = reading_lines(buttons[0], "payment")
					await table._click(labels[0].get_global_rect().get_center())
					await settled()
			else:
				check(int(table.model.summary().revision) == revision + int(scenario.steps), "a complete unique pick applies without an extra click")
		await settled()
		check(int(table.model.summary().revision) == revision + int(scenario.steps), "expected actions reached the engine")
		check_receipt(seat)
		await capture_evidence("applied-" + str(scenario.kind) + ("-space-first" if scenario.get("space_first", false) else ""))
		if scenario.has("partner"):
			check(table.model.summary().get("decision", {}).get("kind") != "graft_partner", "the selected graft partner follows once")
	if failed:
		quit(1)
		return
	print("GODOT_PARITY_OK %d" % checks)
	await table._quit_cleanly()
