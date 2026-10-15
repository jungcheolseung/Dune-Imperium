extends Button

# One accessible button owns both the actor heading and the public log text.
var inset: MarginContainer
var labels: Array[Label] = []


func setup(table: Control, heading: String, words: String, color: Color, undone: bool, latest: bool, full_text: String) -> void:
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	tooltip_text = full_text
	accessibility_name = full_text
	for state in ["normal", "hover", "pressed", "focus"]:
		var style = table._style(Color("242c31") if state in ["hover", "pressed"] else Color("1c2328"), Color("e8c78a") if state in ["hover", "focus"] else color.darkened(0.45) if latest else Color("35414b"))
		style.border_width_left = 3
		add_theme_stylebox_override(state, style)
	inset = MarginContainer.new()
	inset.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for key in ["margin_left", "margin_right"]:
		inset.add_theme_constant_override(key, 8)
	for key in ["margin_top", "margin_bottom"]:
		inset.add_theme_constant_override(key, 6)
	add_child(inset)
	var body = VBoxContainer.new()
	body.add_theme_constant_override("separation", 4)
	inset.add_child(body)
	var header = HBoxContainer.new()
	header.add_theme_constant_override("separation", 4)
	body.add_child(header)
	var who = table._label(header, "", 12)
	who.text = heading
	who.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	who.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	who.add_theme_color_override("font_color", color)
	who.set_meta("history_heading", true)
	labels.append(who)
	if undone or latest:
		labels.append(table._label(header, table.model.native("되돌림" if undone else "최근"), 11))
	var detail = table._label(body, "", 13)
	detail.text = words
	detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail.set_meta("history_body", true)
	labels.append(detail)
	if undone:
		modulate.a = 0.55
	table._ignore_mouse(inset)
	inset.minimum_size_changed.connect(_fit_height)
	resized.connect(_fit_height)
	_fit_height.call_deferred()


func _fit_height() -> void:
	custom_minimum_size.y = ceilf(maxf(50, inset.get_combined_minimum_size().y))


func layout_fits() -> bool:
	return labels.all(func(label): return get_global_rect().grow(1).encloses(label.get_global_rect()))
