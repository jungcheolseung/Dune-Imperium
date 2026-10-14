extends RefCounted

var table: Control


func render(actions: Array) -> void:
	var payload = table.model.snapshot.get("actions")
	if not payload is Dictionary:
		return
	var boxes = payload.get("agent_boxes")
	if not boxes is Array:
		boxes = []
	var scouts = payload.get("scouts_lines")
	var lines = scouts.get("lines", []) if scouts is Dictionary else []
	var waiting = payload.get("unavailable", {}).get("rows", []) if payload.get("unavailable") is Dictionary else []
	var headed = false
	for box in boxes:
		var count = actions.filter(func(action): return action.get("box") == box.box).size() + waiting.filter(func(row): return row.get("box") == box.box).size()
		headed = headed or (count >= 2 if boxes.size() == 1 else count > 0 or box.get("locked", false))
	if headed:
		for box in boxes:
			var rows = actions.filter(func(action): return action.get("box") == box.box)
			var disabled = waiting.filter(func(row): return row.get("box") == box.box)
			if rows.is_empty() and disabled.is_empty() and not box.get("locked", false):
				continue
			table._label(table.content, table.model.ui("render.agent_box_heading", {"name": table.model.localized(box, "name")}), 17).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			if box.get("locked", false):
				table._label(table.content, table.model.ui("render.agent_box_locked"), 13).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			_rows(rows, disabled, [])
		var other = actions.filter(func(action): return action.get("box") == null)
		var other_disabled = waiting.filter(func(row): return row.get("box") == null)
		if not other.is_empty() or not other_disabled.is_empty():
			table._label(table.content, table.model.ui("render.agent_box_others_heading"), 17)
			_rows(other, other_disabled, lines)
	else:
		_rows(actions, waiting, lines)


func _rows(actions: Array, waiting: Array, lines: Variant) -> void:
	var groups: Dictionary = {}
	var order: Array = []
	for action in actions:
		var key = "action:" + str(action.index)
		var count_key = ""
		var fixed = action.arguments.duplicate(true)
		for field in ["count", "amount", "bid", "troops"]:
			if fixed.get(field) is int or fixed.get(field) is float:
				count_key = field
				fixed.erase(field)
				break
		if not count_key.is_empty():
			key = table.model.quantity_key(action, count_key)
		if not groups.has(key):
			groups[key] = {"field": count_key, "actions": []}
			order.append(key)
		groups[key].actions.append(action)
	var descriptions: Dictionary = {}
	if lines is Array:
		for line in lines:
			if line.get("action_index") != null:
				descriptions[int(line.action_index)] = table.model.phrase(table.model.localized(line, "text"))
			else:
				_unavailable_line(table.model.phrase(table.model.localized(line, "text")), table.model.phrase(table.model.localized(line, "reason")))
	for key in order:
		var group = groups[key]
		var count_control = not group.field.is_empty() and (group.actions.size() >= 3 or group.actions[0].action_id in table.Model.AUCTION_AMOUNTS or group.actions[0].action_id in table.Model.FORCE_AMOUNTS)
		if not count_control:
			for action in group.actions:
				table._action_button(action, descriptions.get(int(action.index), ""))
		else:
			_quantity(group.actions, group.field, descriptions)
	for row in waiting:
		_unavailable_line(table.model.describe(row.action), table.model.phrase(table.model.localized(row, "reason")), row.get("refs", []))


func _quantity(actions: Array, field: String, descriptions: Dictionary) -> void:
	actions = actions.duplicate()
	actions.sort_custom(func(a, b): return int(a.arguments[field]) < int(b.arguments[field]))
	var auction = actions[0].action_id in table.Model.AUCTION_AMOUNTS
	var body = VBoxContainer.new()
	var panel = table._panel(table.content, 8)
	panel.add_child(body)
	var title = table._label(body, table.model.label("ACTION_LABELS", str(actions[0].action_id)), 15)
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var row = HBoxContainer.new()
	body.add_child(row)
	var select = OptionButton.new()
	select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	select.set_meta("quantity_actions", actions)
	select.set_meta("quantity_field", field)
	var indices: Array = []
	for action in actions:
		indices.append(int(action.index))
		var unit = table.model.phrase("{" + table.model.scouts_currency() + "}") if auction else table.model.label("PAYLOAD_KEY_LABELS", field)
		select.add_item(str(int(action.arguments[field])) + " " + unit)
	select.set_meta("action_indices", indices)
	row.add_child(select)
	select.select(indices.find(int(table.model.selected_quantity(actions, field).index)))
	var held = table.model.held_action()
	if not held.is_empty() and int(held.index) in indices:
		select.select(indices.find(int(held.index)))
	var expected = table.model.signature()
	var detail = table._label(body, "", 13)
	detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var submit: Button
	if not auction:
		submit = table._button(row, table.model.native("선택 / Choose"), func(): table._choose_action(actions[select.selected], expected))
	var update = func():
		var action = actions[select.selected]
		if submit != null:
			submit.text = table.model.ui("render.confirm_count_label", {"count": int(action.arguments[field]), "label": title.text})
			submit.set_meta("action_index", int(action.index))
			submit.set_meta("action_indices", indices)
			submit.set_meta("quantity_select", select)
			submit.disabled = table.busy
		detail.text = descriptions.get(int(action.index), table.model.describe(action))
		select.disabled = table.busy or actions.size() == 1
	update.call()
	select.item_selected.connect(func(_index):
		if expected == table.model.signature() and table.model.stage_quantity(actions[select.selected], field):
			table._render()
	)
	for value in actions[0].arguments.values():
		if submit != null and value is String and not table.model.entry(value).is_empty():
			table._bind_preview(submit, value)
			break


func _unavailable_line(title: String, reason: String, refs: Array = []) -> void:
	var button = table._button(table.content, title + "\n" + reason, func(): pass)
	button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.disabled = true
	button.tooltip_text = reason
	button.set_meta("unavailable_reason", reason)
	for ref in refs:
		if ref is String and not table.model.entry(ref).is_empty():
			table._bind_preview(button, ref)
			break
