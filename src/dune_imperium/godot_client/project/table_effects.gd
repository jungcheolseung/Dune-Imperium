extends Node

var table: Control
var previous: Dictionary = {}
var banner: PanelContainer
var body: HBoxContainer
var queue: Array = []
var playing = false
var audio: AudioStreamPlayer
var tones: Dictionary = {}
var sequence = 0
var hold: Timer
var fade: Tween


func setup(owner_table: Control) -> void:
	table = owner_table
	banner = table._panel(table.board, 10)
	banner.z_index = 11
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	banner.hide()
	audio = AudioStreamPlayer.new()
	add_child(audio)
	hold = Timer.new()
	hold.one_shot = true
	add_child(hold)
	hold.timeout.connect(func():
		fade = create_tween()
		fade.tween_property(banner, "modulate:a", 0.0, 0.18)
		fade.tween_callback(_next)
	)
	for cue in ["decision", "round", "combat", "scouts"]:
		tones[cue] = _tone(cue)


static func changes(before: Dictionary, after: Dictionary, reviewing: bool) -> Array:
	var result: Array = []
	var old = before.get("summary", {})
	var state = after.get("summary", {})
	if reviewing or old.is_empty() or old.get("game_id") != state.get("game_id") or old.get("undo_count") != state.get("undo_count") or int(state.get("revision", 0)) < int(old.get("revision", 0)):
		return result
	if not before.get("view") is Dictionary or not after.get("view") is Dictionary or before.view.get("player") != after.view.get("player"):
		return result
	if state.get("finished", false) and not old.get("finished", false):
		result.append({"kind": "finished"})
	elif state.get("round_number") != old.get("round_number"):
		result.append({"kind": "round", "round": state.get("round_number")})
	elif state.get("phase") == "combat" and old.get("phase") != "combat":
		result.append({"kind": "combat"})
	if after.view.get("scouts_item", "") != before.view.get("scouts_item", "") and not str(after.view.get("scouts_item", "")).is_empty():
		result.append({"kind": "scouts", "ref": after.view.scouts_item})
	var decision = state.get("decision")
	if decision is Dictionary and decision.get("owner") == after.view.get("player") and (not old.get("decision") is Dictionary or old.decision.get("owner") != decision.owner or old.decision.get("decision_id") != decision.get("decision_id")):
		result.append({"kind": "decision"})
	var players = before.view.get("players", [])
	for player in after.view.get("players", []):
		var seat = int(player.player)
		if seat >= players.size():
			continue
		var delta: Dictionary = {}
		for key in ["spice", "solari", "water"]:
			var change = int(player.get("resources", {}).get(key, 0)) - int(players[seat].get("resources", {}).get(key, 0))
			if change:
				delta[key] = change
		var vp = int(player.victory_points) - int(players[seat].victory_points)
		if vp:
			delta.victory_point = vp
		if not delta.is_empty():
			result.append({"kind": "resources", "seat": seat, "delta": delta})
		for ref in player.get("in_play", []):
			if ref not in players[seat].get("in_play", []):
				result.append({"kind": "played", "seat": seat, "ref": ref})
	# Acquisitions are taken from the authorized log, never a hidden deck diff.
	var entries = before.get("log", {}).get("entries", [])
	var last = int(entries[-1].index) if not entries.is_empty() else -1
	for entry in after.get("log", {}).get("entries", []):
		if int(entry.index) > last and not entry.get("undone", false) and entry.get("type") == "action" and str(entry.get("action_id", "")).begins_with("acquire_"):
			for field in ["card_id", "tech_id"]:
				if entry.get("arguments", {}).get(field) is String:
					result.append({"kind": "acquired", "seat": entry.get("actor", -1), "ref": entry.arguments[field]})
	return result


func observe() -> void:
	var snapshot = table.model.snapshot
	var events = changes(previous, snapshot, not table.tools_ui.review.is_empty())
	var old_view = previous.get("view")
	var old_seat = old_view.get("player", -1) if old_view is Dictionary else -1
	var invalidated = previous.get("summary", {}).get("game_id") != snapshot.get("summary", {}).get("game_id") or previous.get("summary", {}).get("undo_count") != snapshot.get("summary", {}).get("undo_count") or old_seat != table.model.active_seat or not table.tools_ui.review.is_empty()
	previous = snapshot.duplicate(true)
	if invalidated:
		shutdown()
	if not table.tools_ui.prefs.get("animations", true) or table.tools_ui.prefs.get("reduced_motion", false):
		queue.clear()
		banner.hide()
		for event in events:
			if event.kind in tones:
				sound(str(event.kind))
		return
	for event in events:
		if queue.size() < 12:
			queue.append(event)
	if not playing:
		_next()


func _next() -> void:
	playing = false
	if queue.is_empty():
		banner.hide()
		return
	playing = true
	var event = queue.pop_front()
	var cue = str(event.kind)
	if cue in tones:
		sound(cue)
	if not table.tools_ui.prefs.get("animations", true) or table.tools_ui.prefs.get("reduced_motion", false):
		queue.clear()
		playing = false
		return
	table._clear(banner)
	body = HBoxContainer.new()
	banner.add_child(body)
	var title = ""
	match event.kind:
		"round": title = table.model.ui("screens.round_number", {"round": int(event.round)})
		"combat": title = table.model.label("PHASE_LABELS", "combat")
		"finished": title = table.model.native("게임 종료 · 최종 순위")
		"scouts": title = table.model.ui("render.scouts_decision_secrets") if event.ref == "secrets" else table.model.name_of(event.ref)
		"decision": title = table.model.native("내 차례 · ") + table.model.prompt()
		"played", "acquired":
			title = table.model.seat_name(int(event.seat)) + " · " + table.model.label("EVENT_LABELS", "card_acquired" if event.kind == "acquired" else "card_played") + "\n" + table.model.name_of(event.ref)
			table._picture(body, table._image_path(table.model.entry(event.ref)), Vector2(88, 125))
		"resources":
			var words: PackedStringArray = []
			for key in event.delta:
				words.append(table.model.phrase("{" + key + "}") + " " + ("+" if int(event.delta[key]) > 0 else "") + str(int(event.delta[key])))
			title = table.model.seat_name(int(event.seat)) + "\n" + " · ".join(words)
	var label = table._label(body, title, 17)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size.x = clampf(table.board.size.x - 140, 180, 390)
	banner.reset_size()
	banner.position = Vector2(12, 12)
	banner.modulate.a = 1
	table._ignore_mouse(banner)
	banner.show()
	hold.start(0.65 if event.kind == "resources" else 0.95)


func shutdown() -> void:
	sequence += 1
	queue.clear()
	playing = false
	if hold != null:
		hold.stop()
	if fade != null:
		fade.kill()
	if is_instance_valid(banner):
		banner.hide()
	if audio != null:
		audio.stop()


func sound(cue: String) -> void:
	var volume = clampf(float(table.tools_ui.prefs.get("volume", 0.35)), 0, 1)
	if not table.tools_ui.prefs.get("sound", true) or volume <= 0:
		return
	audio.volume_db = linear_to_db(volume)
	audio.stream = tones[cue]
	audio.play()


func _tone(cue: String) -> AudioStreamWAV:
	var notes: Array = []
	match cue:
		"decision": notes = [[587.3, 0.0, 0.13], [880.0, 0.15, 0.2]]
		"round": notes = [[1046.5, 0.0, 1.4], [2093.0, 0.0, 0.8], [3135.9, 0.0, 0.4]]
		"combat": notes = [[110.0, 0.0, 1.1], [220.0, 0.0, 0.7], [331.0, 0.0, 0.5]]
		"scouts": notes = [[523.3, 0.0, 0.14], [659.3, 0.09, 0.14], [784.0, 0.18, 0.23]]
	var rate = 22050
	var bytes = PackedByteArray()
	bytes.resize(rate * 2 * 2)
	for index in range(rate * 2):
		var time = float(index) / rate
		var sample = 0.0
		for note in notes:
			var age = time - note[1]
			if age < 0 or age >= note[2]:
				continue
			var wave = sin(TAU * note[0] * age)
			if cue == "scouts":
				wave = asin(wave) * 2 / PI
			var envelope = minf(1, age / 0.008) * exp(-age * 5 / note[2]) * (1 - age / note[2])
			sample += wave * envelope * 0.2
		bytes.encode_s16(index * 2, clampi(roundi(sample * 32767), -32768, 32767))
	var stream = AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.data = bytes
	return stream
