extends RefCounted

var table: Control
var dialog: AcceptDialog
var body: VBoxContainer
var path: Array = []
var seat = -1
var refs: Array = []
var shown: Array = []
var selected = ""
var picture: TextureRect
var heading: Label
var words: Label
var filter: LineEdit
var count: Label
var before = ""
var preserve_order = false


func open(owner_table: Control, title: String, cards: Array, order = false) -> AcceptDialog:
	table = owner_table
	seat = table.model.active_seat
	refs = cards.duplicate()
	preserve_order = order and table.model.view().get("disclosure") is Dictionary
	path = _find(table.model.view().disclosure, cards) if preserve_order else _find(table.model.view(), cards)
	if preserve_order and not path.is_empty():
		path = ["disclosure"] + path
	dialog = AcceptDialog.new()
	dialog.title = title
	dialog.theme = table.theme
	dialog.ok_button_text = table.model.ui("common.close")
	dialog.set_meta("game_dialog", table.game_id)
	dialog.set_meta("pile_viewer", self)
	var root = VBoxContainer.new()
	root.custom_minimum_size = Vector2(940, 535)
	dialog.add_child(root)
	var bar = HBoxContainer.new()
	root.add_child(bar)
	filter = LineEdit.new()
	filter.placeholder_text = table.model.native("카드 이름 검색")
	filter.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(filter)
	count = table._label(bar, "", 14)
	var row = HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(row)
	body = table._scroll(row)
	body.get_parent().custom_minimum_size.x = 520
	var side = VBoxContainer.new()
	side.custom_minimum_size.x = 385
	side.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(side)
	heading = table._label(side, "", 20)
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	picture = table._picture(side, "", Vector2(240, 280))
	picture.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var description = table._scroll(side)
	words = table._label(description, "", 16)
	words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	filter.text_changed.connect(func(_text): render())
	table._attach_dialog(dialog)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	render()
	dialog.popup_centered()
	return dialog


func _find(value: Variant, target: Array) -> Array:
	if value is Dictionary:
		for key in value:
			if value[key] is Array and value[key] == target and not target.is_empty():
				return [key]
			var found = _find(value[key], target)
			if not found.is_empty():
				return [key] + found
	elif value is Array:
		for index in value.size():
			var found = _find(value[index], target)
			if not found.is_empty():
				return [index] + found
	return []


func refresh() -> void:
	if not is_instance_valid(dialog):
		return
	if seat != table.model.active_seat:
		dialog.hide()
		dialog.queue_free()
		return
	if not path.is_empty():
		var current: Variant = table.model.view()
		for key in path:
			if current is Dictionary:
				current = current.get(key)
			elif current is Array and key is int and key < current.size():
				current = current[key]
			else:
				current = null
		refs = current.duplicate() if current is Array else []
	var key = JSON.stringify(refs) + table.model.language
	if key != before:
		render()


func render() -> void:
	before = JSON.stringify(refs) + table.model.language
	table._clear(body)
	var groups: Dictionary = {}
	for ref in refs:
		var id = table.model.section_id(str(ref))
		var key = ":".join(id)
		if not groups.has(key):
			groups[key] = {"ref": str(ref), "count": 0}
		groups[key].count += 1
	shown = []
	if preserve_order:
		for index in refs.size():
			shown.append({"ref": str(refs[index]), "count": 1, "ordinal": index + 1})
	else:
		shown = groups.values()
		shown.sort_custom(func(a, b): return table.model.name_of(a.ref).naturalnocasecmp_to(table.model.name_of(b.ref)) < 0)
	shown = shown.filter(func(group): return filter.text.is_empty() or filter.text.to_lower() in table.model.name_of(group.ref).to_lower())
	count.text = table.model.native("%d장") % refs.size()
	if refs.is_empty():
		table._label(body, table.model.native("카드가 없습니다."), 18)
	var row: HBoxContainer
	for index in shown.size():
		if index % 3 == 0:
			row = HBoxContainer.new()
			body.add_child(row)
		var group = shown[index]
		var cell = VBoxContainer.new()
		row.add_child(cell)
		var card = table._card(cell, group.ref, 162, 212, false)
		for signal_name in ["pressed", "mouse_entered", "mouse_exited", "gui_input"]:
			for connection in card.get_signal_connection_list(signal_name):
				card.disconnect(signal_name, connection.callable)
		card.mouse_entered.connect(inspect.bind(group.ref))
		card.pressed.connect(inspect.bind(group.ref))
		table._label(cell, ("#%d" % int(group.ordinal)) if preserve_order else "×%d" % int(group.count), 13).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if not refs.is_empty():
		inspect(selected if selected in refs else str(refs[0]))
	else:
		picture.texture = null
		picture.set_meta("image_path", "")
		heading.text = ""
		words.text = ""


func inspect(ref: String) -> void:
	selected = ref
	heading.text = table.model.name_of(ref)
	words.text = table._entry_words(table.model.entry(ref), ref)
	picture.ref = ref
	var image = table._image_path(table.model.entry(ref))
	picture.set_meta("image_path", image)
	picture.texture = table.api.texture(image)
