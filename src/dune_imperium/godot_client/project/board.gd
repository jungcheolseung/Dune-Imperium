extends Control

signal chosen(ref: String)
signal inspected(ref: String)

const Model = preload("res://model.gd")
var model: RefCounted
var board_texture: Texture2D
var conflict_texture: Texture2D
var map_rect = Rect2()
var hovered = ""
var phase_time = 0.0
var agents: Dictionary = {}
var previous_agents: Dictionary = {}
var move_started = 0.0
var zoom = 1.0
var pan = Vector2.ZERO


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	resized.connect(queue_redraw)
	mouse_exited.connect(func(): hovered = ""; queue_redraw())


func refresh() -> void:
	previous_agents = agents.duplicate()
	agents.clear()
	for player in model.view().get("players", []):
		for location in player.get("agent_locations", []):
			agents["%s:%s" % [player.player, location]] = {"seat": int(player.player), "space": location}
	move_started = Time.get_ticks_msec() / 1000.0
	queue_redraw()


func _process(delta: float) -> void:
	phase_time += delta
	if not model.selected_card.is_empty() or Time.get_ticks_msec() / 1000.0 - move_started < 0.6:
		queue_redraw()


func _point(x: float, y: float) -> Vector2:
	return map_rect.position + map_rect.size * Vector2(x, y) / 100.0


func _box(box: Array) -> Rect2:
	return Rect2(_point(box[0], box[1]), map_rect.size * Vector2(box[2], box[3]) / 100.0)


func _draw() -> void:
	var side = minf(size.x - 16, size.y - 16)
	if side <= 0:
		return
	map_rect = Rect2((size - Vector2.ONE * side * zoom) / 2 + pan, Vector2.ONE * side * zoom)
	draw_rect(map_rect, Color("191e22"))
	if board_texture != null:
		draw_texture_rect(board_texture, map_rect, false)
	else:
		draw_string(get_theme_default_font(), map_rect.position + Vector2(20, 32), "아라키스 · 그림 없이도 칸을 선택할 수 있습니다", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("b2ac9e"))
	if model == null:
		return
	var legal = model.legal_refs()
	for id in model.catalog.get("spaces", {}):
		var entry = model.catalog.spaces[id]
		if entry.get("box") == null or entry.get("required_leader_id") != null:
			continue
		var rect = _box(entry.box)
		var enabled = legal.has(id)
		var active = id == hovered or id == model.selected_space
		if enabled or active or board_texture == null:
			var accent = Color("e5bf7d") if enabled else Color("72899d")
			draw_rect(rect.grow(2), Color(accent, 0.15 if not active else 0.32))
			draw_rect(rect.grow(2), accent, false, 2.5 if active else 1.4)
			if board_texture == null or active or (enabled and not model.selected_card.is_empty()):
				var caption = Rect2(rect.position + Vector2(-12, -22), Vector2(maxf(rect.size.x + 24, 90), 22))
				draw_rect(caption, Color(0.045, 0.06, 0.075, 0.94))
				draw_string(get_theme_default_font(), caption.position + Vector2(4, 16), model.name_of(id), HORIZONTAL_ALIGNMENT_LEFT, caption.size.x - 8, 13, Color("f1e4ce"))
	for post in model.catalog.get("posts", {}):
		var point = model.catalog.posts[post]
		if legal.has(post):
			draw_circle(_point(point[0], point[1]), side * 0.012, Color("e5bf7d"), false, 2.0, true)
	for key in agents:
		var marker = agents[key]
		var entry = model.entry(marker.space)
		if entry.get("box") == null:
			continue
		var target = _box(entry.box).get_center() + Vector2((marker.seat - 1.5) * 9, 0)
		var elapsed = clampf((Time.get_ticks_msec() / 1000.0 - move_started) / 0.45, 0, 1)
		if not previous_agents.has(key):
			var start = map_rect.position + Vector2(map_rect.size.x * (marker.seat + 0.5) / 4, map_rect.size.y)
			target = start.lerp(target, 1 - pow(1 - elapsed, 3))
		draw_circle(target, 10, Color("091018"), true, -1, true)
		draw_circle(target, 8, Model.SEAT_COLORS[marker.seat], true, -1, true)
		draw_string(get_theme_default_font(), target + Vector2(-4, 4), str(marker.seat + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color.WHITE)
	_draw_tracks(side)
	if conflict_texture != null:
		var box = model.catalog.get("tracks", {}).get("conflict_slot")
		if box is Array:
			draw_texture_rect(conflict_texture, _box(box), false)


func _draw_tracks(side: float) -> void:
	var tracks = model.catalog.get("tracks", {})
	var influence = tracks.get("influence", {})
	var victory = tracks.get("victory_points", {})
	for player in model.view().get("players", []):
		var seat = int(player.player)
		var color = Model.SEAT_COLORS[seat]
		if not influence.is_empty():
			for faction in influence.get("offsets", {}):
				var level = clampi(int(player.get("influence", {}).get(faction, 0)), 0, influence.levels.size() - 1)
				var point = _point(influence.seat_x[seat], influence.levels[level] + influence.offsets[faction])
				draw_rect(Rect2(point - Vector2.ONE * side * 0.008, Vector2.ONE * side * 0.016), color)
		if not victory.is_empty():
			var score = clampi(int(player.victory_points), 0, victory.levels.size() - 1)
			draw_circle(_point(victory.x + (seat - 1.5) * 0.8, victory.levels[score]), side * 0.009, color, true, -1, true)
		for post in player.get("spy_post_ids", []):
			var point = model.catalog.get("posts", {}).get(post)
			if point is Array:
				draw_circle(_point(point[0], point[1]) + Vector2(seat * 3, 0), 5, color, true, -1, true)


func _hit(position: Vector2) -> String:
	for post in model.catalog.get("posts", {}):
		var point = model.catalog.posts[post]
		if model.legal_refs().has(post) and position.distance_to(_point(point[0], point[1])) < 15:
			return post
	for id in model.catalog.get("spaces", {}):
		var entry = model.catalog.spaces[id]
		if entry.get("box") != null and entry.get("required_leader_id") == null and _box(entry.box).has_point(position):
			return id
	return ""


func reset_view() -> void:
	zoom = 1.0
	pan = Vector2.ZERO
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_MIDDLE:
			pan += event.relative
			queue_redraw()
			accept_event()
			return
		var hit = _hit(event.position)
		if hit != hovered:
			hovered = hit
			if not hit.is_empty():
				inspected.emit(hit)
			queue_redraw()
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		var previous = zoom
		zoom = clampf(zoom * (1.15 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.15), 1.0, 3.0)
		pan = (event.position - size / 2) - (event.position - size / 2 - pan) * zoom / previous
		queue_redraw()
		accept_event()
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var hit = _hit(event.position)
		if not hit.is_empty():
			chosen.emit(hit)
			accept_event()
