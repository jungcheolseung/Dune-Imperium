extends "res://parity_test.gd"


func pause_layout() -> void:
	await table._wait_images()
	await process_frame
	await process_frame


func close_dialog(dialog: Window) -> void:
	dialog.confirmed.emit()
	await process_frame
	await process_frame


func inspect_dialog(dialog: Window, label: String) -> void:
	await pause_layout()
	table._fit_columns()
	check(Rect2(Vector2.ZERO, table.size).encloses(Rect2(Vector2(dialog.position), Vector2(dialog.size))), label + ": dialog fits the logical viewport")
	for detail in dialog.find_children("*", "BoxContainer", true, false):
		if detail.has_meta("entry_view"):
			check(detail.layout_fits(), label + ": artwork and text have separate reading areas")
			check(detail.heading.text == table.model.name_of(detail.ref), label + ": complete catalog name is present")


func market_case(scenario: Dictionary) -> void:
	var contract_refs = table.model.view().get("face_up_contract_ids", [])
	for group in [["face_up_contract_ids", "contracts"], ["tech_face_up", "tech"], ["skill_face_up", "skills"]]:
		var refs = table.model.view().get(group[0], [])
		if not check(not refs.is_empty(), "legal fixture supplies " + group[1]):
			continue
		var ref = str(refs[0])
		var card = table._ref_button(table.market_content, ref)
		if not check(card != null, "expanded market keeps its actual card control"):
			continue
		table.market_scroll.ensure_control_visible(card)
		await pause_layout()
		check(card.face.size.x >= 140 and card.face.size.y >= 80, "landscape artwork has a readable surface")
		check(card.caption.text == table.model.name_of(ref), "landscape card has its own localized name")
		await capture_evidence("market-" + group[1] + "-" + scenario.language)
	var pile = table._open_pile(table.model.native("초암 계약"), contract_refs)
	await inspect_dialog(pile, "contract pile")
	var viewer = pile.get_meta("pile_viewer")
	var copies = 0
	for group in viewer.shown:
		copies += int(group.count)
	check(copies == contract_refs.size(), "contract gallery retains every authorized copy")
	if viewer.picture.texture != null:
		check(viewer.picture.custom_minimum_size.y <= 220, "landscape preview returns space to its description")
	await capture_evidence("contracts-" + scenario.language)
	await close_dialog(pile)
	var leader = str(table.model.view().players[0].leader_id)
	for player in table.model.view().players:
		if str(player.leader_id) == "shaddam_corrino_iv":
			leader = str(player.leader_id)
	table._open_details(leader)
	var dialogs = table.find_children("*", "Window", true, false).filter(func(window): return window.has_meta("detail_ref") and not window.is_queued_for_deletion())
	if check(dialogs.size() == 1, "leader detail opens once"):
		await inspect_dialog(dialogs[0], "leader")
		await capture_evidence("leader-" + scenario.language)
		await close_dialog(dialogs[0])
	var parts = table.tools_ui._dialog(table.model.native("초암 계약"), Vector2i(920, 600))
	var ref = str(contract_refs[0])
	var entry = table.model.entry(ref).duplicate(true)
	entry.image = null
	entry.erase("image_ko")
	var detail = table._entry_panel(parts[1], ref, entry)
	await inspect_dialog(parts[0], "no artwork")
	check(not detail.picture.visible and detail.words.text.length() > 0, "missing artwork keeps the full description and reclaims its column")
	check(detail.body.size.x > 700, "missing artwork does not reserve an empty picture column")
	await capture_evidence("no-artwork-" + scenario.language)
	await close_dialog(parts[0])


func research_case(scenario: Dictionary) -> void:
	var action: Dictionary = {}
	for offered in table.model.actions():
		if int(offered.index) == int(scenario.index):
			action = offered
	var points = table.model.catalog.bene_tleilax.layout.research_points
	var target = ""
	for value in action.get("arguments", {}).values():
		if value is String and points.has(value):
			target = value
	if not check(not target.is_empty(), "research route comes from an offered server action"):
		return
	var dialog = table.expansions.open_bene()
	await inspect_dialog(dialog, "research")
	var board = dialog.get_meta("research_board")
	var choices = dialog.find_children("*", "Button", true, false).filter(func(button): return button.has_meta("research_ref"))
	var legal: Array = []
	for ref in points:
		if table.model.legal_refs().has(ref):
			legal.append(ref)
	check(choices.size() == legal.size() and choices.all(func(button): return str(button.get_meta("research_ref")) in legal), "research buttons expose exactly the server's legal destinations")
	await capture_evidence("research-" + scenario.language)
	await pause_layout()
	var capture = Array(OS.get_cmdline_user_args()).any(func(argument): return argument.begins_with("--evidence="))
	if capture:
		var point = Vector2(dialog.position) + board.get_global_transform() * board._point(points[target])
		await table._click(point)
	else:
		var button = choices.filter(func(item): return str(item.get_meta("research_ref")) == target)[0]
		button.pressed.emit()
	await settled()
	check(not is_instance_valid(dialog) or dialog.is_queued_for_deletion(), "choosing research closes the inspection dialog")


func scouts_case(scenario: Dictionary) -> void:
	table.tools_ui.prefs.scouts_folded = false
	table.expansions.scouts_manual = true
	table.expansions._update_scouts()
	await pause_layout()
	var panel = table.expansions.scouts_panel
	check(panel.visible, "current Scouts item remains accessible")
	check(table.board.get_global_rect().encloses(panel.get_global_rect()), "Scouts overlay stays inside its board")
	await capture_evidence("scouts-overlay-" + scenario.language)
	var details = table.expansions.scouts_details()
	await inspect_dialog(details, "Scouts details")
	await capture_evidence("scouts-details-" + scenario.language)
	await close_dialog(details)
	var closes = panel.find_children("*", "Button", true, false).filter(func(button): return button.get_meta("scouts_close", false))
	if check(closes.size() == 1, "Scouts overlay has one reachable close control"):
		await table._click(closes[0].get_global_rect().get_center())
		check(not panel.visible, "closing Scouts returns to the game board")


func run() -> void:
	var timer = Timer.new()
	timer.one_shot = true
	timer.wait_time = 220
	timer.timeout.connect(func(): push_error("GODOT_PANEL_TIMEOUT"); quit(1))
	root.add_child(timer)
	timer.start()
	table = load("res://main.tscn").instantiate()
	table.tools_ui.prefs_file = directory + "/panels-ui.json"
	table.api.cookie_file = directory + "/panels-cookies.json"
	root.add_child(table)
	while table.model.catalog.is_empty() or table.tools_ui.table == null:
		await process_frame
	table.tools_ui.prefs.clear()
	table.tools_ui.prefs.animations = false
	table.tools_ui.prefs.sound = false
	for scenario in scenarios:
		if not check(await table._adopt_game(str(scenario.game)), "adopt expansion fixture"):
			continue
		await settled()
		table.model.language = str(scenario.language)
		table._render()
		await pause_layout()
		var before = table.model.signature()
		if scenario.kind == "market":
			await market_case(scenario)
		elif scenario.kind == "research":
			await research_case(scenario)
		else:
			await scouts_case(scenario)
		await settled()
		if scenario.kind != "research":
			check(table.model.signature() == before, "read-only panels never send an action")
	if failed:
		quit(1)
		return
	print("GODOT_PANELS_OK %d" % checks)
	await table._quit_cleanly()
