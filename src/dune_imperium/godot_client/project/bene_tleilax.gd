extends Control

signal chosen(ref: String)
var model: RefCounted
var api: Node
var map_rect = Rect2()
var hovered = ""
var before = ""


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(queue_redraw)
	api.texture_ready.connect(func(_path, _texture): queue_redraw())


func _process(_delta: float) -> void:
	var key = model.signature() + JSON.stringify(model.legal_refs())
	if key != before:
		before = key
		queue_redraw()


func _point(point: Array) -> Vector2:
	return map_rect.position + Vector2(point[0], point[1]) * map_rect.size / 100


func _draw() -> void:
	var data = model.catalog.get("bene_tleilax", {})
	var layout = data.get("layout", {})
	var path = data.get("image")
	var picture = api.texture(str(path)) if path != null else null
	var ratio = float(layout.get("aspect", 5551.0 / 3952))
	var dimensions = Vector2(minf(size.x, size.y * ratio), minf(size.y, size.x / ratio))
	map_rect = Rect2((size - dimensions) / 2, dimensions)
	if picture != null:
		draw_texture_rect(picture, map_rect, false)
	else:
		draw_rect(map_rect, Color("293330"))
	var legal = model.legal_refs()
	for ref in layout.get("research_points", {}):
		var point = _point(layout.research_points[ref])
		var radius = dimensions.x * 0.03
		if picture == null or legal.has(ref) or hovered == ref:
			draw_circle(point, radius, Color("e4bb76") if legal.has(ref) else Color("667f71"), false, 2)
			if picture == null:
				draw_string(get_theme_default_font(), point + Vector2(-radius, 4), model.name_of(ref), HORIZONTAL_ALIGNMENT_LEFT, radius * 2, 10, Color.WHITE)
	for player in model.view().get("players", []):
		var seat = int(player.player)
		var research = layout.get("research_points", {}).get(str(player.research_space))
		if research is Array:
			draw_circle(_point(research) + Vector2(seat * 3 - 4, -dimensions.x * 0.018), dimensions.x * 0.009, model.SEAT_COLORS[seat])
		var cells = layout.get("track_cells", [])
		var position = clampi(int(player.tleilaxu_space), 0, cells.size() - 1)
		if not cells.is_empty():
			var cell = cells[position]
			var y = layout.get("track_band", [3, 19.5])[0] + 7 + seat * 2
			draw_circle(_point([cell[0] + cell[1] / 2, y]), dimensions.x * 0.009, model.SEAT_COLORS[seat])
		var tanks = layout.get("specimens", {}).get("boxes", [])
		if tanks.size() > seat and int(player.specimens) > 0:
			var box = tanks[seat]
			var point = _point([box[0] + box[2] / 2, box[1] + box[3] / 2])
			draw_circle(point, dimensions.x * 0.02, model.SEAT_COLORS[seat])
			draw_string(get_theme_default_font(), point + Vector2(-4, 4), str(int(player.specimens)), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE)
	var spice = int(model.view().get("tleilaxu_track_spice", 0))
	if spice > 0 and layout.get("spice_point") is Array:
		var point = _point(layout.spice_point)
		draw_circle(point, dimensions.x * 0.015, Color("c98431"))
		draw_string(get_theme_default_font(), point + Vector2(-4, 4), str(spice), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE)
	var scouts = layout.get("scouts", {})
	for good in model.view().get("scouts_goods", []):
		if good[1] == "helix" and scouts.get("helix_spice_point") is Array:
			var point = _point(scouts.helix_spice_point)
			draw_circle(point, dimensions.x * 0.025, Color("775021"))
			draw_string(get_theme_default_font(), point + Vector2(-4, 4), str(int(good[3])), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE)
	for parked in model.view().get("scouts_parked", []):
		if parked[2] != "tleilaxu_track":
			continue
		var regions = scouts.get("regions", {}).get("tleilaxu_track", [])
		if regions.is_empty():
			continue
		var box = regions[0].box
		var seat = int(parked[1])
		var point = _point([box[0] + box[2] * (0.25 + (seat % 2) * 0.5), box[1] + box[3] * (0.25 + int(seat / 2) * 0.5)])
		draw_rect(Rect2(point - Vector2.ONE * dimensions.x * 0.01, Vector2.ONE * dimensions.x * 0.02), model.SEAT_COLORS[seat])
		draw_string(get_theme_default_font(), point + Vector2(-3, 4), str(int(parked[3])), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color.WHITE)


func _hit(position: Vector2) -> String:
	var layout = model.catalog.get("bene_tleilax", {}).get("layout", {})
	for ref in layout.get("research_points", {}):
		if position.distance_to(_point(layout.research_points[ref])) <= map_rect.size.x * 0.04:
			return ref
	return ""


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		hovered = _hit(event.position)
		tooltip_text = model.name_of(hovered) if not hovered.is_empty() else model.phrase("{bene_tleilax_board}")
		queue_redraw()
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var ref = _hit(event.position)
		if model.legal_refs().has(ref):
			chosen.emit(ref)
			accept_event()
