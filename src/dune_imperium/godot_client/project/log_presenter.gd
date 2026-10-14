extends RefCounted

var table: Control


func render(parent: VBoxContainer) -> void:
	var scroll = parent.get_parent()
	var anchor = -1
	var offset = 0.0
	for child in parent.get_children():
		if child.has_meta("log_index") and scroll.get_global_rect().intersects(child.get_global_rect()):
			anchor = int(child.get_meta("log_index"))
			offset = child.global_position.y - scroll.global_position.y
			break
	table._clear(parent)
	var entries = table.model.snapshot.get("log", {}).get("entries", [])
	for index in range(entries.size() - 1, maxi(-1, -1 if parent == table.content else entries.size() - 41), -1):
		var entry = entries[index]
		var text = ""
		match entry.get("type"):
			"action": text = table.model.seat_name(int(entry.get("actor", -1))) + " · " + table.model.describe(entry)
			"undo": text = table.model.ui("panels.undo_row", {"seat": int(entry.get("seat", -1)), "count": int(entry.get("count", 0))})
			_:
				var names: PackedStringArray = []
				for event in entry.get("events", []):
					names.append(table.model.label("EVENT_LABELS", str(event.get("kind", ""))))
				text = " · ".join(names)
		if text.is_empty():
			continue
		if entry.get("undone", false):
			text += table.model.ui("panels.undone_suffix")
		var line = table._label(parent, text, 12)
		line.set_meta("log_index", int(entry.get("index", -1)))
		line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		line.mouse_filter = Control.MOUSE_FILTER_STOP
		line.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		if entry.get("undone", false):
			line.modulate.a = 0.5
		line.gui_input.connect(func(event):
			if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
				details(entry)
		)
		for value in entry.get("arguments", {}).values():
			if value is String and not table._image_path(table.model.entry(value)).is_empty():
				table._bind_preview(line, value)
				break
	var restore = func():
		if not is_instance_valid(scroll):
			return
		if table.tools_ui.prefs.get("log_follow", true):
			scroll.scroll_vertical = 0
		else:
			for child in parent.get_children():
				if int(child.get_meta("log_index", -2)) == anchor:
					scroll.scroll_vertical += roundi(child.global_position.y - scroll.global_position.y - offset)
					break
	restore.call_deferred()


func details(entry: Dictionary) -> Window:
	var parts = table.tools_ui._dialog(table.model.native("행동 기록"))
	if entry.get("type") == "action":
		table._label(parts[1], table.model.seat_name(int(entry.get("actor", -1))) + "\n" + table.model.describe(entry), 18).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for event in entry.get("events", []):
		table._label(parts[1], table.model.label("EVENT_LABELS", str(event.get("kind", ""))), 17)
		_payload(parts[1], event.get("payload", {}))
	return parts[0]


func _payload(parent: Node, data: Variant, depth = 0) -> void:
	if depth > 4:
		return
	if data is Dictionary:
		for key in data:
			if key in ["effect_key", "visibility", "rng_state"]:
				continue
			var value = data[key]
			if value is Dictionary:
				table._label(parent, table.model.label("PAYLOAD_KEY_LABELS", str(key)), 14)
				_payload(parent, value, depth + 1)
			else:
				var text = table.model.label("PAYLOAD_KEY_LABELS", str(key)) + ": "
				if value is Array:
					var names: PackedStringArray = []
					for item in value:
						if item is String:
							names.append(table.model.name_of(item))
						elif item is int or item is float:
							names.append(str(int(item)))
						else:
							_payload(parent, item, depth + 1)
					text += " / ".join(names)
				elif value is String:
					text += table.model.name_of(value) if str(key).ends_with("_id") or not table.model.entry(value).is_empty() else table.model.phrase(value)
				elif value is int or value is float:
					text += table.model.seat_name(int(value)) if key in ["player", "first_player", "from_player", "to_player", "recipient", "victim", "visitor"] else str(int(value))
				elif value is bool:
					text += "✓" if value else "—"
				else:
					continue
				table._label(parent, text, 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
