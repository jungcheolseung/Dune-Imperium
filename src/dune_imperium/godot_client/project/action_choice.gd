extends Button

# The complete reading surface belongs to one button; clicking a cost or
# warning follows the same guarded callback as clicking its action title.
var table: Control
var reading: Dictionary
var inset: MarginContainer
var body: VBoxContainer
var labels: Array[Label] = []


func setup(owner_table: Control, action: Dictionary, description: String, zone: String, ref: String, callback: Callable) -> void:
	table = owner_table
	reading = table.model.choice_reading(action, description, zone)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	custom_minimum_size.y = 48
	tooltip_text = (description if not description.is_empty() else table.model.live_description(action)) + table.model.choice_suffix(zone)
	accessibility_name = reading.title
	accessibility_description = tooltip_text
	set_meta("action_index", int(action.index))
	if action.get("placement") != null:
		set_meta("placement", int(action.placement))
	set_meta("choice_suffix", table.model.choice_suffix(zone))
	set_meta("action_reading", true)
	if action.get("box") != null:
		set_meta("agent_box", int(action.box))
	disabled = table.busy
	pressed.connect(callback)
	_surface(ref)
	labels = populate(table, body, reading)
	if int(table.model.held_action().get("index", -1)) == int(action.index):
		labels.append(line(table, body, "held", table.model.native("✓ 선택됨 · 턴 종료로 확정"), 13, Color("bce7d0")))
		accessibility_description += "\n" + table.model.native("✓ 선택됨 · 턴 종료로 확정")
		add_theme_stylebox_override("normal", table._style(Color("263b36"), Color("81c5ab")))
	table._ignore_mouse(inset)


func setup_unavailable(owner_table: Control, title: String, reason: String) -> void:
	table = owner_table
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	disabled = true
	tooltip_text = reason
	accessibility_name = title
	accessibility_description = reason
	set_meta("unavailable_reason", reason)
	set_meta("action_reading", true)
	_surface("")
	labels.append(line(table, body, "title", title, 14, Color("a6b0b8")))
	if not reason.is_empty():
		labels.append(line(table, body, "warning", table.model.native("선택 불가") + " · " + reason, 13, Color("d7b58b")))
	table._ignore_mouse(inset)


func _surface(ref: String) -> void:
	inset = MarginContainer.new()
	inset.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for key in ["margin_left", "margin_right"]:
		inset.add_theme_constant_override(key, 10)
	for key in ["margin_top", "margin_bottom"]:
		inset.add_theme_constant_override(key, 9)
	add_child(inset)
	var row = HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	inset.add_child(row)
	if not ref.is_empty() and not table._image_path(table.model.entry(ref)).is_empty():
		var picture = table._picture(row, table._image_path(table.model.entry(ref)), Vector2(36, 51))
		picture.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	body = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 5)
	row.add_child(body)
	inset.minimum_size_changed.connect(_fit_height)
	resized.connect(_fit_height)
	_fit_height.call_deferred()


static func populate(owner_table: Control, parent: Node, data: Dictionary, title = true) -> Array[Label]:
	var result: Array[Label] = []
	var rows = [["title", data.title if title else "", 16, Color("edf0f2")], ["context", data.context + data.zone, 13, Color("b5c2cc")], ["payment", data.payment, 13, Color("a4dcec")], ["effect", data.effect, 14, Color("e0e7eb")]]
	for preview in data.previews:
		rows.append(["preview", preview, 13, Color("a4dcec")])
	for warning in data.warnings:
		rows.append(["warning", warning, 13, Color("f2ca89")])
	for row in rows:
		if str(row[1]).is_empty():
			continue
		var prefix = {"effect": "효과", "preview": "예상", "warning": "주의"}.get(row[0], "")
		var words = (owner_table.model.native(prefix) + " · " if not prefix.is_empty() else "") + str(row[1])
		result.append(line(owner_table, parent, row[0], words, row[2], row[3]))
	return result


static func line(owner_table: Control, parent: Node, kind: String, words: String, font_size: int, color: Color) -> Label:
	var label = owner_table._label(parent, "", font_size)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", color)
	label.set_meta("reading_kind", kind)
	label.text = words
	return label


func _fit_height() -> void:
	custom_minimum_size.y = ceilf(maxf(48, inset.get_combined_minimum_size().y))


func layout_fits() -> bool:
	var bounds = get_global_rect().grow(1)
	return labels.all(func(label): return bounds.encloses(label.get_global_rect()))
