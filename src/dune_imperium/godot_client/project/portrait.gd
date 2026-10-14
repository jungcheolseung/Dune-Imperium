extends TextureRect

var model: RefCounted
var ref = ""
var previous = ""


func _process(_delta: float) -> void:
	if model != null and previous != model.signature():
		previous = model.signature()
		queue_redraw()


func _draw() -> void:
	if texture == null or model == null or ref.is_empty():
		return
	var layout = model.entry(ref).get("layout")
	var player = model.leader_player(ref)
	if not layout is Dictionary or player.is_empty():
		return
	var aspect = float(texture.get_width()) / texture.get_height()
	var dimensions = Vector2(minf(size.x, size.y * aspect), minf(size.y, size.x / aspect))
	var origin = (size - dimensions) / 2
	var track = layout.get("track")
	var box: Array = []
	if track is Dictionary:
		box = track.get(str(player.get("feyd_track_space", "")), [])
	elif track is Array and not track.is_empty():
		box = track[clampi(int(player.get("tactics_track_space", 0)), 0, track.size() - 1)]
	if box.size() == 4:
		var point = origin + Vector2(box[0] + box[2] / 2, box[1] + box[3] / 2) * dimensions / 100
		var radius = maxf(2, dimensions.x * 0.015)
		draw_circle(point, radius + 1, Color.WHITE)
		draw_circle(point, radius, model.SEAT_COLORS[int(player.player)])
