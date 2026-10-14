extends RefCounted

const NativeText = preload("res://native_text.gd")


func native(text: String) -> String:
	return str(NativeText.EN.get(text, text)) if language == "en" else text

const END_ACTIONS = ["finish_agent_turn", "finish_reveal", "finish_leader_draft", "pass_combat_intrigue", "pass_endgame_intrigue", "decline_conflict_end_intrigue"]
const SEAT_COLORS = [Color("438bde"), Color("d66063"), Color("42ac87"), Color("e4b955")]
const SECTIONS = ["cards", "intrigue", "leaders", "spaces", "conflicts", "objectives", "contracts", "skills", "tech", "scouts_items"]
const EXPANSIONS = ["choam_module", "promo_cards", "bloodlines", "tech_module", "immortality", "go_to_11", "epic_game", "arrakeen_scouts"]

var catalog: Dictionary = {}
var words: Dictionary = {}
var snapshot: Dictionary = {}
var language = "ko"
var selected_card = ""
var selected_space = ""
var held: Dictionary = {}
var active_seat = 0
var owned_seats: Array = [0]
var server_info: Dictionary = {}


func summary() -> Dictionary:
	return snapshot.get("summary", {})


func view() -> Dictionary:
	var data = snapshot.get("view")
	return data if data is Dictionary else {}


func actions() -> Array:
	var payload = snapshot.get("actions")
	return payload.get("actions", []) if payload is Dictionary else []


func signature() -> String:
	var current = summary()
	return "%s:%s:%s:%s" % [current.get("game_id", ""), current.get("revision", -1), current.get("undo_count", -1), active_seat]


func adopt(data: Dictionary) -> bool:
	var before = signature()
	var previous = snapshot
	snapshot = data
	if data.get("you") is Dictionary:
		owned_seats = data.you.get("seats", []).map(func(seat): return int(seat))
	if view().has("player"):
		active_seat = int(view().player)
	elif data.has("you"):
		active_seat = -1
	var changed = before != signature()
	if changed:
		held.clear()
		selected_card = ""
		selected_space = ""
	# Confirmation and AI activity may change without an engine revision.
	var old_summary = previous.get("summary", {}).duplicate()
	var new_summary = summary().duplicate()
	old_summary.erase("clock")
	new_summary.erase("clock")
	return changed or old_summary != new_summary or previous.get("actions") != data.get("actions") or previous.get("you") != data.get("you")


func seat_name(seat: int) -> String:
	var players = summary().get("players", [])
	if players.size() > seat and seat >= 0:
		var name = players[seat].get("name")
		if name != null and not str(name).is_empty():
			return str(name)
	var kinds = summary().get("seats", [])
	if kinds.size() > seat and seat >= 0 and kinds[seat] == "human":
		return (native("나") if language == "ko" else "You") if seat == active_seat else ui("common.seat", {"seat": seat})
	return (native("나") if language == "ko" else "You") if seat == active_seat else (native("앱 AI %d") if language == "ko" else "AI %d") % seat


func ui(key: String, values: Dictionary = {}) -> String:
	var text = str(words.get("ui", {}).get(key, {}).get(language, key))
	for field in values:
		text = text.replace("{{" + str(field) + "}}", str(values[field]))
	return phrase(text)


func pick_seat(data: Dictionary) -> int:
	var mine = data.get("you", {}).get("seats", []).map(func(seat): return int(seat))
	var state = data.get("summary", {})
	if mine.is_empty():
		return -1
	var confirming = state.get("confirmation")
	if confirming != null and int(confirming) in mine:
		return int(confirming)
	var decision = state.get("decision")
	if confirming == null and decision is Dictionary and int(decision.get("owner", -1)) in mine:
		return int(decision.owner)
	return active_seat if active_seat in mine else int(mine[0])


func finish_action() -> Dictionary:
	for action in actions():
		if action.action_id in END_ACTIONS:
			return action
	return {}


func finish_text() -> String:
	if not held_action().is_empty():
		return native("선택 확정 ▶")
	var action = finish_action()
	return label("ACTION_LABELS", action.action_id) + " ▶" if not action.is_empty() else native("턴 종료 ▶")


func supported_save(saved: Dictionary) -> bool:
	if saved.has("error"):
		return false
	var seats = saved.get("seats", [])
	if seats.size() != 4:
		return false
	var config = saved.get("ruleset", {})
	if not config is Dictionary or int(config.get("players", 0)) != 4:
		return false
	return true


func section_id(ref: String) -> Array[String]:
	if ref.begins_with("contract:"):
		return ["contracts", ref.trim_prefix("contract:")]
	var parts = ref.split(":")
	if parts.size() >= 5 and parts[0] == "player" and parts[2] == "starter":
		return ["cards", parts[3]]
	if parts.size() >= 3:
		var sections = {"imperium": "cards", "reserve": "cards", "tleilaxu": "cards", "intrigue": "intrigue", "skill": "skills"}
		if sections.has(parts[0]):
			return [sections[parts[0]], parts[1]]
	return ["", ref]


func entry(ref: String) -> Dictionary:
	var parsed = section_id(ref)
	if not parsed[0].is_empty():
		return catalog.get(parsed[0], {}).get(parsed[1], {})
	for section in SECTIONS:
		if catalog.get(section, {}).has(parsed[1]):
			var found = catalog[section][parsed[1]]
			if section == "spaces":
				var effective = found.duplicate()
				if summary().get("choam_module", false) and found.get("choam_options") is Array:
					effective.options = found.choam_options
				if summary().get("immortality", false) and found.get("immortality") is Dictionary:
					effective.erase("image_ko")
					effective.merge(found.immortality, true)
				return effective
			return found
	for space in catalog.get("bene_tleilax", {}).get("research_spaces", []):
		if space.id == ref:
			return {"name": "Research %d-%d" % [int(space.column), int(space.row)], "name_ko": "연구 %d-%d" % [int(space.column), int(space.row)], "text": [label("RESEARCH_BONUS_LABELS", str(space.bonus))]}
	return {}


func localized(data: Dictionary, key: String) -> Variant:
	var translated = data.get(key + "_ko") if language == "ko" else null
	return translated if translated != null else data.get(key)


func name_of(ref: String) -> String:
	var found = entry(ref)
	if not found.is_empty():
		return str(localized(found, "name"))
	var values = words.get(language, {}).get("VALUE_LABELS", {})
	if values.has(ref):
		return phrase(values[ref])
	var factions = words.get(language, {}).get("FACTION_LABELS", {})
	return str(factions.get(ref, ref.replace("_", " ").capitalize()))


func phrase(value: Variant) -> String:
	if value == null:
		return ""
	var result = str(value)
	var regex = RegEx.new()
	regex.compile("\\{([a-z_]+)(?::([0-9]+))?\\}")
	for found in regex.search_all(result):
		var term = words.get("terms", {}).get(found.get_string(1), {})
		var text = term.get(language, found.get_string(1).replace("_", " "))
		if not found.get_string(2).is_empty():
			text += " " + found.get_string(2)
		result = result.replace(found.get_string(), text)
	return result


func label(table: String, key: String) -> String:
	return phrase(words.get(language, {}).get(table, {}).get(key, key.replace("_", " ").capitalize()))


func prompt() -> String:
	var decision = summary().get("decision")
	if not decision is Dictionary:
		return ""
	var text = str(decision.get("prompt", ""))
	if language != "ko":
		return phrase(text)
	if words.get("prompts", {}).has(text):
		return phrase(words.prompts[text])
	for pattern in words.get("prompt_patterns", []):
		var regex = RegEx.new()
		if regex.compile(pattern[0]) != OK:
			continue
		var found = regex.search(text)
		if found != null:
			var translated = str(pattern[1])
			for index in range(1, found.get_group_count() + 1):
				translated = translated.replace("$" + str(index), found.get_string(index))
			return phrase(translated)
	return phrase(text)


func placements(card: String = "", space: String = "") -> Array:
	var result: Array = []
	for action in actions():
		var args = action.get("arguments", {})
		if action.get("action_id") == "agent_turn" and (card.is_empty() or args.get("card_id") == card) and (space.is_empty() or args.get("space_id") == space):
			result.append(action)
	return result


func ref_actions(ref: String) -> Array:
	var result: Array = []
	for action in actions():
		if _contains_ref(action.get("arguments", {}), ref):
			result.append(action)
	return result


func _contains_ref(value: Variant, ref: String) -> bool:
	if value is String:
		return value == ref
	if value is Dictionary:
		return _contains_ref(value.values(), ref)
	if value is Array:
		for part in value:
			if _contains_ref(part, ref):
				return true
	return false


func unavailable(ref: String) -> Dictionary:
	var rows = snapshot.get("actions")
	if rows is Dictionary and rows.get("unavailable") is Dictionary:
		return rows.unavailable.get("refs", {}).get(ref, {})
	return {}


func legal_refs() -> Dictionary:
	var result: Dictionary = {}
	for action in actions():
		if action.get("action_id") == "agent_turn" and not selected_card.is_empty() and action.arguments.get("card_id") != selected_card:
			continue
		for value in action.get("arguments", {}).values():
			if value is String:
				result[value] = true
	return result


func cost_text(cost: Dictionary) -> String:
	var parts: PackedStringArray = []
	for key in ["solari", "spice", "water"]:
		var amount = int(cost.get(key, 0))
		if amount:
			parts.append("%s %d" % [phrase("{" + key + "}"), amount])
	return " · ".join(parts)


func describe(action: Dictionary) -> String:
	var args = action.get("arguments", {})
	var title = localized(action, "detail_title")
	var detail = localized(action, "detail")
	var heading = phrase(title) if title != null else label("ACTION_LABELS", action.get("action_id", ""))
	var parts: PackedStringArray = []
	if detail != null and not str(detail).is_empty():
		parts.append(phrase(detail))
	for key in args:
		var value = args[key]
		if key in ["effect_key", "box", "cost_option"] or (value is String and value.is_empty()):
			continue
		if key == "effect" and detail != null:
			continue
		if key == "option" and action.get("action_id") == "play_intrigue":
			var lines = localized(entry(str(args.get("card_id", ""))), "text")
			if lines is Array and int(value) < lines.size():
				parts.append(phrase(lines[int(value)]))
				continue
		var field = label("PAYLOAD_KEY_LABELS", key)
		if value is String and (not entry(value).is_empty() or key in ["faction", "faction_id", "space_id", "post_id"]):
			if key == "post_id":
				var spaces = catalog.get("post_spaces", {}).get(value, [])
				var names: PackedStringArray = []
				for space in spaces:
					names.append(name_of(space))
				parts.append(native("관측소 · ") + " / ".join(names))
			else:
				parts.append(field + ": " + name_of(value))
		elif value is bool:
			if value:
				parts.append(field)
		elif value is int or value is float:
			parts.append(field + ": " + (seat_name(int(value)) if key in ["player", "target_player", "opponent", "from_player", "to_player"] else str(int(value))))
		elif value is Array:
			var names: PackedStringArray = []
			for ref in value:
				names.append(name_of(str(ref)))
			parts.append(field + ": " + " / ".join(names))
		elif value is String:
			parts.append(field + ": " + name_of(value))
	if args.has("cost_option") and args.has("space_id"):
		var options = entry(args.space_id).get("options", [])
		var index = int(args.cost_option)
		if index < options.size():
			parts.append(cost_text(options[index].get("cost", {})) + " → " + phrase(localized(options[index], "effect")))
	if action.get("strength_after") != null:
		parts.append(native("전투력 → %d") % int(action.strength_after))
	if action.get("reveal_preview") is Dictionary:
		parts.append(native("공개 후 설득력 %d · 전투력 %d") % [int(action.reveal_preview.get("persuasion", 0)), int(action.reveal_preview.get("strength", 0))])
	if action.get("shortfall") is Array:
		for shortage in action.shortfall:
			var data = shortage.duplicate()
			data["short"] = int(data.requested) - int(data.made)
			data["tile"] = name_of("suspensor_suits")
			var key = "render.shortfall_" + str(data.kind)
			if data.kind == "intrigue" and int(data.get("twisted", 0)) > 0:
				key += "_twisted"
			parts.append(ui(key, data))
	elif action.get("warning") != null and language == "ko":
		parts.append(phrase(action.warning))
	if action.get("undoable") == false and not action.get("sent_by_turn_end", false):
		parts.append(ui("render.irreversible_badge"))
	return heading + ("\n" + " · ".join(parts) if not parts.is_empty() else "")


func hold(action: Dictionary) -> void:
	held = {"signature": signature(), "index": int(action.index), "choice": JSON.stringify([action.action_id, action.get("arguments", {})])}


func held_action() -> Dictionary:
	if held.get("signature") != signature():
		return {}
	for action in actions():
		if int(action.index) == int(held.get("index", -1)) and action.get("sent_by_turn_end", false) and held.get("choice") == JSON.stringify([action.action_id, action.get("arguments", {})]):
			return action
	return {}


func request_body(action: Dictionary) -> Dictionary:
	return {"seat": active_seat, "revision": int(summary().get("revision", -1)), "undo_count": int(summary().get("undo_count", -1)), "index": int(action.index)}


func clock_reading(clock: Dictionary, age: float) -> Dictionary:
	var seats = clock.get("seat_ms", [0, 0, 0, 0]).duplicate()
	var running = clock.get("running")
	var left = maxf(0, age)
	var spell = float(clock.get("spell_ms", 0)) if running != null else 0.0
	for segment in clock.get("narration", []):
		var spent = minf(left, float(segment[1]))
		seats[int(segment[0])] += spent
		if segment[0] == running:
			spell += spent
		left -= spent
		if spent < float(segment[1]):
			break
	if left > 0 and running != null:
		seats[int(running)] += left
		spell += left
	return {"elapsed": float(clock.get("elapsed_ms", 0)) + (maxf(0, age) if clock.get("counting", false) else 0), "seats": seats, "spell": spell}


func clock_text(milliseconds: float) -> String:
	var seconds = maxi(0, int(milliseconds / 1000))
	return "%d:%02d:%02d" % [seconds / 3600, (seconds / 60) % 60, seconds % 60] if seconds >= 3600 else "%d:%02d" % [seconds / 60, seconds % 60]


func turn_stops(steps: Array) -> Array:
	var result: Array = []
	var last: Dictionary = {}
	var passes = ["pass_combat_intrigue", "pass_endgame_intrigue", "decline_conflict_end_intrigue"]
	for index in range(steps.size()):
		var step = steps[index]
		if step.get("type") != "action":
			continue
		if not last.is_empty():
			var closed = last.action_id in END_ACTIONS or last.action_id == "pick_leader" or step.actor != last.actor
			if closed and not (last.action_id in passes and step.action_id in passes):
				result.append(index)
		last = step
	result.append(steps.size())
	return result


func reviewed_log(meta: Dictionary, cursor: int) -> Array:
	var live: Array = []
	var log = meta.get("log", [])
	for entry in log:
		if entry.get("type") != "undo" and not entry.get("undone", false):
			live.append(int(entry.index))
	if cursor <= 0:
		return []
	if cursor >= live.size():
		return log.duplicate()
	return log.slice(0, live[cursor - 1] + 1)


func leader_player(ref: String) -> Dictionary:
	for player in view().get("players", []):
		if player.get("leader_id") == ref or player.get("leader_face_id") == ref:
			return player
	return {}


func offered(action: Dictionary) -> bool:
	for current in actions():
		if int(current.index) == int(action.get("index", -1)) and current.action_id == action.get("action_id") and current.get("arguments", {}) == action.get("arguments", {}):
			return true
	return false
