extends RefCounted

var table: Control


const UNAVAILABLE_HEADINGS = {"acquire": "render.unavailable_acquire_heading", "choice": "render.unavailable_choice_heading", "intrigue": "render.unavailable_intrigue_heading", "waiting": "render.unavailable_waiting_heading"}


func render(actions: Array) -> void:
	var payload = table.model.payload()
	if not payload is Dictionary:
		return
	var decision = table.model.summary().get("decision")
	if decision is Dictionary and decision.get("kind") == "reveal":
		_reveal(actions, payload)
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
			var heading = table._label(table.content, table.model.ui("render.agent_box_heading", {"name": table.model.localized(box, "name")}), 17)
			heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			heading.set_meta("agent_box", int(box.box))
			if box.get("locked", false) and rows.is_empty() and disabled.is_empty():
				var note = table._label(table.content, table.model.ui("render.agent_box_locked"), 13)
				note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
				note.set_meta("locked_box", int(box.box))
			_rows(rows, disabled, [])
		# A row whose box has no heading (render.js: every row not placed in a
		# group) still shows, under the others.
		var headed_boxes = boxes.map(func(box): return box.box)
		var other = actions.filter(func(action): return action.get("box") == null or action.get("box") not in headed_boxes)
		var other_disabled = waiting.filter(func(row): return row.get("box") == null or row.get("box") not in headed_boxes)
		if not other.is_empty() or not other_disabled.is_empty():
			table._label(table.content, table.model.ui("render.agent_box_others_heading"), 17)
			_rows(other, other_disabled, lines)
	else:
		_rows(actions, waiting, lines)


# A Reveal is a small shop (render.js renderRevealPanel): what was bought,
# the Reveal effects left, each revealed card's choice under its own heading
# with whether it may be left, what cannot be taken now, then the cards that
# can be bought. Every choice of a revealed card waits on the Reveal frame
# (codec v147, OQ-095 (7)); the server names the card each row belongs to.
func _reveal(actions: Array, payload: Dictionary) -> void:
	var model = table.model
	var bought = model.bought_this_reveal()
	if not bought.is_empty():
		var line = table._label(table.content, model.ui("render.bought_cards_label") + ", ".join(bought.map(func(card): return model.name_of(str(card)))), 13)
		line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		line.set_meta("reveal_bought", bought)
	var unavailable = payload.get("unavailable")
	var greyed: Array = unavailable.get("rows", []) if unavailable is Dictionary else []
	var buys = actions.filter(func(action): return str(action.action_id).begins_with("acquire"))
	var effects = actions.filter(func(action): return not str(action.action_id).begins_with("acquire"))
	var entries = payload.get("reveal_choices")
	var groups: Array = []
	var grouped: Dictionary = {}
	for entry in entries if entries is Array else []:
		var key = entry.get("key")
		var rows = effects.filter(func(action): return action.get("reveal_choice") == key)
		if rows.is_empty():
			continue
		groups.append({"entry": entry, "rows": rows, "greyed": greyed.filter(func(row): return row.get("reveal_choice") == key and row.get("surface") == "choice")})
		grouped[key] = true
	var others = effects.filter(func(action): return action.get("reveal_choice") == null or not grouped.has(action.reveal_choice))
	if not others.is_empty():
		_heading(model.ui("render.reveal_effects_heading"), "reveal_effects")
		_rows(others, [], [])
	var placed: Dictionary = {}
	for group in groups:
		var entry = group.entry
		var heading = _heading(str(model.localized(entry, "name")) + " — " + model.phrase(model.localized(entry, "text")), "reveal_choice", 16)
		heading.set_meta("reveal_choice", entry.get("key"))
		var note = table._label(table.content, model.ui("render.reveal_choice_optional" if entry.get("optional", false) else "render.reveal_choice_mandatory"), 13)
		note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		note.set_meta("reveal_choice_note", bool(entry.get("optional", false)))
		_rows(group.rows, [], [])
		for row in group.greyed:
			_unavailable_line(model.describe(row.action), model.phrase(model.localized(row, "reason")), row.get("refs", []))
			placed[row.get("key")] = true
	for surface in ["choice", "waiting", "intrigue"]:
		_unavailable_group(greyed, surface, placed)
	if not buys.is_empty():
		_heading(model.ui("render.buyable_cards_heading"), "buyable")
		_rows(buys, [], [])
	_unavailable_group(greyed, "acquire", {})


func _heading(text: String, kind: String, size = 15) -> Label:
	var heading = table._label(table.content, text, size)
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.set_meta("choice_heading", kind)
	return heading


func _unavailable_group(greyed: Array, surface: String, placed: Dictionary) -> void:
	var rows = greyed.filter(func(row): return row.get("surface") == surface and not placed.has(row.get("key")))
	if rows.is_empty():
		return
	_heading(table.model.ui(UNAVAILABLE_HEADINGS[surface]), "unavailable_" + surface)
	for row in rows:
		_unavailable_line(table.model.describe(row.action), table.model.phrase(table.model.localized(row, "reason")), row.get("refs", []))


func _rows(actions: Array, waiting: Array, lines: Variant) -> void:
	var suffixes = table.model.choice_zones(actions)
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
	# Fold quantities first; only the remaining physical card rows form pile runs.
	var rows: Array = []
	var zones: Dictionary = {}
	for key in order:
		var group = groups[key]
		var count_control = not group.field.is_empty() and (group.actions.size() >= 3 or group.actions[0].action_id in table.Model.AUCTION_AMOUNTS or group.actions[0].action_id in table.Model.FORCE_AMOUNTS)
		if count_control:
			rows.append({"group": group, "zone": ""})
		else:
			for action in group.actions:
				var zone = table.model.own_card_zone(str(action.arguments.get("card_id", "")))
				rows.append({"action": action, "zone": zone})
				if not zone.is_empty():
					zones[zone] = true
	var run = ""
	for index in range(rows.size()):
		var row = rows[index]
		if zones.size() >= 2 and row.zone != run:
			if not row.zone.is_empty():
				var count = 0
				while index + count < rows.size() and rows[index + count].zone == row.zone:
					count += 1
				var word = table.model.phrase("{" + row.zone + "}")
				var heading = table._label(table.content, table.model.ui("render.zone_heading", {"zone": word.left(1).to_upper() + word.substr(1), "count": count}), 13)
				heading.set_meta("choice_zone", row.zone)
				heading.set_meta("zone_count", count)
			else:
				table.content.add_child(HSeparator.new())
			run = row.zone
		if row.has("action"):
			table._action_button(row.action, descriptions.get(int(row.action.index), ""), str(suffixes.get(int(row.action.index), "")))
		else:
			_quantity(row.group.actions, row.group.field, descriptions)
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
	# Stack amount and submit controls so long localized labels cannot force
	# the entire decision column beyond the viewport's width.
	var row = VBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	body.add_child(row)
	var select = OptionButton.new()
	select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	select.custom_minimum_size.y = 34
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
	var detail = VBoxContainer.new()
	detail.add_theme_constant_override("separation", 5)
	body.add_child(detail)
	var submit: Button
	if not auction:
		submit = table._button(row, table.model.native("선택 / Choose"), func(): table._choose_action(actions[select.selected], expected))
		submit.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var update = func():
		var action = actions[select.selected]
		if submit != null:
			submit.text = table.model.ui("render.confirm_count_label", {"count": int(action.arguments[field]), "label": title.text})
			submit.set_meta("action_index", int(action.index))
			submit.set_meta("action_indices", indices)
			submit.set_meta("quantity_select", select)
			submit.disabled = table.busy
		table._clear(detail)
		table.ActionChoice.populate(table, detail, table.model.choice_reading(action, descriptions.get(int(action.index), "")), descriptions.has(int(action.index)))
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
	var button = table.ActionChoice.new()
	table.content.add_child(button)
	button.setup_unavailable(table, title, reason)
	for ref in refs:
		if ref is String and not table.model.entry(ref).is_empty():
			table._bind_preview(button, ref)
			break
