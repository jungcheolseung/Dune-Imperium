extends RefCounted

var table: Control
var dragging = ""
var drag_x = 0.0
var original = 0.0


func setup(owner_table: Control) -> void:
	table = owner_table
	_handle(table.seat_scroll.get_parent(), table.seat_scroll.get_index() + 1, "seats")
	_handle(table.side_stack.get_parent(), table.side_stack.get_index(), "choices")
	_handle(table.market_scroll.get_parent().get_parent(), table.market_scroll.get_parent().get_index(), "market")
	table._fit_columns()


func _handle(parent: Node, index: int, key: String) -> void:
	var grip = Control.new()
	grip.custom_minimum_size.x = 5
	grip.size_flags_vertical = Control.SIZE_EXPAND_FILL
	grip.mouse_default_cursor_shape = Control.CURSOR_HSIZE
	grip.tooltip_text = table.model.native("드래그해서 열 너비 조절")
	parent.add_child(grip)
	parent.move_child(grip, index)
	grip.gui_input.connect(func(event):
		if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				dragging = key
				drag_x = event.global_position.x
				original = widths()[key]
			else:
				dragging = ""
				table.tools_ui.save_preferences()
		elif event is InputEventMouseMotion and dragging == key:
			var columns = table.tools_ui.prefs.get("columns", {})
			columns[key] = clampf(original + (event.global_position.x - drag_x) * (1 if key == "seats" else -1), 150 if key != "choices" else 270, 390 if key != "choices" else 520)
			table.tools_ui.prefs.columns = columns
			table._fit_columns()
	)


func widths() -> Dictionary:
	var prefs = table.tools_ui.prefs.get("columns", {})
	var wide = table.size.x >= 1340
	var result = {"seats": float(prefs.get("seats", 210 if wide else 172)), "choices": float(prefs.get("choices", 320 if wide else 280)), "market": float(prefs.get("market", 176 if wide else 160))}
	var minimum = {"seats": 150.0, "choices": 270.0, "market": 150.0}
	var budget = table.size.x - 400
	var total = result.seats + result.choices + (0 if table.tools_ui.prefs.get("market_folded", false) else result.market)
	if total > budget:
		var excess = total - budget
		var spare = (result.seats - minimum.seats) + (result.choices - minimum.choices) + (0 if table.tools_ui.prefs.get("market_folded", false) else result.market - minimum.market)
		for key in result:
			if key != "market" or not table.tools_ui.prefs.get("market_folded", false):
				result[key] = maxf(minimum[key], result[key] - excess * maxf(0, result[key] - minimum[key]) / maxf(1, spare))
	return result


func key(pile: String) -> String:
	return table.api.base_url + ":" + table.game_id + ":" + str(table.model.active_seat) + ":" + pile


func ordered(cards: Array, pile: String) -> Array:
	var saved = table.tools_ui.prefs.get("hand_order", {}).get(key(pile), [])
	var result = saved.filter(func(ref): return ref in cards)
	for ref in cards:
		if ref not in result:
			result.append(ref)
	return result


func move(from_ref: String, to_ref: String, pile: String) -> void:
	var cards = table.model.view().get("private", {}).get(pile, [])
	if from_ref not in cards or to_ref not in cards or from_ref == to_ref:
		return
	var order = ordered(cards, pile)
	order.erase(from_ref)
	order.insert(order.find(to_ref), from_ref)
	var saved = table.tools_ui.prefs.get("hand_order", {})
	saved[key(pile)] = order
	# Bounded preferences; this never changes an engine/save deck or hand.
	while saved.size() > 48:
		saved.erase(saved.keys()[0])
	table.tools_ui.prefs.hand_order = saved
	table.tools_ui.save_preferences()
	table._render()


func reset() -> void:
	table.tools_ui.prefs.erase("columns")
	table.tools_ui.prefs.erase("hand_order")
	table.tools_ui.save_preferences()
	table._fit_columns()
	table._render()


func fold_header(parent: Node, title: String, key: String, inspect: Callable) -> bool:
	var folded = table.tools_ui.prefs.get("folded_groups", {}).get(key, false)
	var row = HBoxContainer.new()
	parent.add_child(row)
	var toggle = table._button(row, "▶" if folded else "▼", func():
		var groups = table.tools_ui.prefs.get("folded_groups", {})
		groups[key] = not folded
		table.tools_ui.prefs.folded_groups = groups
		table.tools_ui.save_preferences()
		table._render()
	)
	toggle.custom_minimum_size = Vector2(25, 26)
	var heading = table._button(row, title, inspect)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.custom_minimum_size.y = 26
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.add_theme_font_size_override("font_size", 12)
	return folded
