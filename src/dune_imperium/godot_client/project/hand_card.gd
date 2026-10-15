extends Button

var table: Control
var ref = ""
var pile = ""
var face: TextureRect
var caption: Label
var fallback: Label


func arrange_face() -> void:
	# Reserve two lines for names, including the small shared-market cards.
	# Resize the face with the button so window/column changes need no snapshot.
	if face == null or caption == null:
		return
	var footer = 34 if size.x < 120 else 38
	face.position = Vector2(4, 4)
	face.size = Vector2(maxf(1, size.x - 8), maxf(1, size.y - footer - 8))
	caption.position = Vector2(5, size.y - footer)
	caption.size = Vector2(maxf(1, size.x - 10), footer - 3)
	var marker_room = size.x - 10
	for child in get_children():
		if child.has_meta("card_cost"):
			marker_room -= child.get_minimum_size().x + 5
	for child in get_children():
		if child.has_meta("card_state"):
			var text = str(child.get_meta("card_state"))
			child.text = text
			if child.get_minimum_size().x > marker_room:
				child.text = text.left(1) if text.left(1) in ["✓", "+", "×", "–", "●"] else "•"
			child.reset_size()
	if fallback != null:
		fallback.position = Vector2(8, 30)
		fallback.size = Vector2(maxf(1, size.x - 16), maxf(1, size.y - footer - 34))


func _get_drag_data(_position: Vector2) -> Variant:
	if table.busy or pile.is_empty() or table.model.active_seat not in table.model.owned_seats or not table.tools_ui.review.is_empty():
		return null
	var preview = TextureRect.new()
	preview.texture = table.api.texture(table._image_path(table.model.entry(ref)))
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	preview.custom_minimum_size = Vector2(90, 128)
	preview.modulate.a = 0.8
	set_drag_preview(preview)
	table._hide_preview()
	return {"kind": "dune_hand", "origin": table.api.base_url, "game": table.game_id, "seat": table.model.active_seat, "pile": pile, "ref": ref}


func _can_drop_data(_position: Vector2, data: Variant) -> bool:
	return not table.busy and not pile.is_empty() and table.tools_ui.review.is_empty() and data is Dictionary and data.get("kind") == "dune_hand" and data.get("origin") == table.api.base_url and data.get("game") == table.game_id and data.get("seat") == table.model.active_seat and data.get("pile") == pile and data.get("ref") in table.model.view().get("private", {}).get(pile, [])


func _drop_data(_position: Vector2, data: Variant) -> void:
	if _can_drop_data(_position, data):
		table.layout_ui.move(data.ref, ref, pile)
