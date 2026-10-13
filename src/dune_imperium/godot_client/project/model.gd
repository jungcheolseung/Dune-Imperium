extends RefCounted

const END_ACTIONS = ["finish_agent_turn", "finish_reveal", "finish_leader_draft", "pass_combat_intrigue", "pass_endgame_intrigue", "decline_conflict_end_intrigue"]
const SEAT_COLORS = [Color("438bde"), Color("d66063"), Color("42ac87"), Color("e4b955")]
const SECTIONS = ["cards", "intrigue", "leaders", "spaces", "conflicts", "objectives", "contracts", "skills", "tech"]

var catalog: Dictionary = {}
var words: Dictionary = {}
var snapshot: Dictionary = {}
var language = "ko"
var selected_card = ""
var selected_space = ""
var held: Dictionary = {}


func summary() -> Dictionary:
	return snapshot.get("summary", {})


func view() -> Dictionary:
	return snapshot.get("view", {})


func actions() -> Array:
	var payload = snapshot.get("actions")
	return payload.get("actions", []) if payload is Dictionary else []


func signature() -> String:
	var current = summary()
	return "%s:%s:%s" % [current.get("game_id", ""), current.get("revision", -1), current.get("undo_count", -1)]


func adopt(data: Dictionary) -> bool:
	var before = signature()
	snapshot = data
	var changed = before != signature()
	if changed:
		held.clear()
		selected_card = ""
		selected_space = ""
	return changed


func section_id(ref: String) -> Array[String]:
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
			return catalog[section][parsed[1]]
	return {}


func localized(data: Dictionary, key: String) -> Variant:
	return data.get(key + "_ko", data.get(key)) if language == "ko" else data.get(key)


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
	return phrase(words.get("prompts", {}).get(text, text)) if language == "ko" else text


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
		if ref in action.get("arguments", {}).values():
			result.append(action)
	return result


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
		if value is String and (not entry(value).is_empty() or key in ["faction", "faction_id", "space_id", "post_id"]):
			if key == "post_id":
				var spaces = catalog.get("post_spaces", {}).get(value, [])
				var names: PackedStringArray = []
				for space in spaces:
					names.append(name_of(space))
				parts.append("관측소 · " + " / ".join(names))
			else:
				parts.append(name_of(value))
		elif (value is int or value is float) and key in ["count", "troops", "amount", "water", "spice", "solari"]:
			parts.append("× %d" % int(value))
	if args.has("cost_option") and args.has("space_id"):
		var options = entry(args.space_id).get("options", [])
		var index = int(args.cost_option)
		if index < options.size():
			parts.append(cost_text(options[index].get("cost", {})) + " → " + phrase(localized(options[index], "effect")))
	if action.get("strength_after") != null:
		parts.append("전투력 → %d" % int(action.strength_after))
	if action.get("warning") != null:
		parts.append(phrase(action.warning))
	return heading + ("\n" + " · ".join(parts) if not parts.is_empty() else "")


func hold(action: Dictionary) -> void:
	held = {"signature": signature(), "index": int(action.index)}


func held_action() -> Dictionary:
	if held.get("signature") != signature():
		return {}
	for action in actions():
		if int(action.index) == int(held.get("index", -1)) and action.get("sent_by_turn_end", false):
			return action
	return {}


func request_body(action: Dictionary) -> Dictionary:
	return {"seat": 0, "revision": int(summary().get("revision", -1)), "undo_count": int(summary().get("undo_count", -1)), "index": int(action.index)}
