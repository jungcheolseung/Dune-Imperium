extends RefCounted

const NativeText = preload("res://native_text.gd")


func native(text: String) -> String:
	return str(NativeText.EN.get(text, text)) if language == "en" else text

const END_ACTIONS = ["finish_agent_turn", "finish_reveal", "finish_leader_draft", "pass_combat_intrigue", "pass_endgame_intrigue", "decline_conflict_end_intrigue", "confirm_scouts_bid", "scouts_call"]
const AUCTION_AMOUNTS = ["scouts_bid", "scouts_call"]
const FORCE_AMOUNTS = ["deploy_troops", "withdraw_troops", "deploy_commanders", "withdraw_commanders"]
const SEAT_COLORS = [Color("438bde"), Color("d66063"), Color("42ac87"), Color("e4b955")]
const SECTIONS = ["cards", "intrigue", "leaders", "spaces", "conflicts", "objectives", "contracts", "skills", "tech", "scouts_items"]
const EXPANSIONS = ["choam_module", "promo_cards", "bloodlines", "tech_module", "immortality", "go_to_11", "epic_game", "arrakeen_scouts"]
const DECK_TOP_CHOICES = {"put_back_top_card": "panels.deck_top_put_back", "discard_top_card": "panels.deck_top_discard", "draw_top_card_for_solari": "panels.deck_top_draw"}

var catalog: Dictionary = {}
var words: Dictionary = {}
var snapshot: Dictionary = {}
var language = "ko"
var selected_card = ""
var selected_space = ""
var selected_partner = ""
var held: Dictionary = {}
var local_counts: Dictionary = {}
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
		local_counts.clear()
		clear_pick()
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
			return selected_quantity(actions().filter(func(row): return row.action_id == "scouts_call")) if action.action_id == "scouts_call" else action
	return {}


func finish_text() -> String:
	if not held_action().is_empty():
		return native("선택 확정 ▶")
	var action = finish_action()
	var currency = scouts_currency()
	if not action.is_empty() and not currency.is_empty() and action.action_id in ["confirm_scouts_bid", "scouts_call"]:
		var amount = selected_quantity(actions().filter(func(row): return row.action_id == "scouts_bid")) if action.action_id == "confirm_scouts_bid" else action
		var count = int(amount.get("arguments", {}).get("count", 0))
		var key = "render.turn_end_bid" if action.action_id == "confirm_scouts_bid" else "render.turn_end_pass_call" if count == 0 else "render.turn_end_call"
		return ui(key, {"resource": phrase("{" + currency + "}"), "count": count})
	return label("ACTION_LABELS", action.action_id) + " ▶" if not action.is_empty() else native("턴 종료 ▶")


func scouts_currency() -> String:
	var payload = snapshot.get("actions")
	var item = view().get("scouts_item", "")
	if payload is Dictionary and payload.get("scouts_lines") is Dictionary:
		item = payload.scouts_lines.get("item_id", item)
	return str(catalog.get("scouts_items", {}).get(str(item), {}).get("currency", ""))


func quantity_key(action: Dictionary, field: String) -> String:
	var keys = action.get("arguments", {}).keys()
	keys.erase(field)
	keys.sort()
	var fixed: Array = []
	for key in keys:
		fixed.append([key, action.arguments[key]])
	return str(action.action_id) + ":" + field + ":" + JSON.stringify(fixed)


func selected_quantity(family: Array, field = "count") -> Dictionary:
	if family.is_empty():
		return {}
	var sorted = family.duplicate()
	sorted.sort_custom(func(a, b): return int(a.arguments[field]) < int(b.arguments[field]))
	var id = str(sorted[0].action_id)
	var key = quantity_key(sorted[0], field)
	var count = local_counts.get(key, max(0, int(view().get("private", {}).get("scouts_bid", 0))) if id == "scouts_bid" else null)
	for action in sorted:
		if count != null and int(action.arguments[field]) == int(count):
			return action
	return sorted[-1] if id.begins_with("deploy") else sorted[0]


func stage_quantity(action: Dictionary, field = "count") -> bool:
	if not offered(action):
		return false
	local_counts[quantity_key(action, field)] = int(action.arguments[field])
	var picked = held_action()
	if not picked.is_empty() and picked.action_id == action.action_id and int(picked.index) != int(action.index):
		held.clear()
	return true


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


func placements(card: String = "", space: String = "", partner: String = "") -> Array:
	var result: Array = []
	var options: Dictionary = {}
	for action in actions():
		var args = action.get("arguments", {})
		if action.get("action_id") != "agent_turn" or (not space.is_empty() and args.get("space_id") != space):
			continue
		if partner.is_empty():
			if card.is_empty() or args.get("card_id") == card:
				result.append(action)
		elif args.get("graft", false) and args.get("card_id") in [card, partner]:
			# The browser presents symmetric DTOs as one option, preferring
			# the first picked card. Never manufacture a new action/index.
			var keys = args.keys()
			keys.erase("card_id")
			keys.sort()
			var option: Array = []
			for key in keys:
				option.append([key, args[key]])
			var identity = JSON.stringify(option)
			if not options.has(identity) or args.get("card_id") == card:
				options[identity] = action
	if not partner.is_empty():
		result = options.values()
	return result


func picked_placements() -> Array:
	return placements(selected_card, selected_space, selected_partner)


func can_pair(card: String, other: String) -> bool:
	var hand = view().get("private", {}).get("hand", [])
	if card == other or card not in hand or other not in hand:
		return false
	if not entry(card).get("graft", false) and not entry(other).get("graft", false):
		return false
	return actions().any(func(action): return action.action_id == "agent_turn" and action.arguments.get("graft", false) and action.arguments.get("card_id") in [card, other])


func clear_pick(part = "") -> void:
	if part.is_empty():
		selected_card = ""
		selected_space = ""
		selected_partner = ""
	elif part == "space":
		selected_space = ""
	elif part == "partner":
		selected_partner = ""
	elif part == "card":
		selected_card = selected_partner
		selected_partner = ""


func pick_step(ref: String) -> String:
	var joins = not selected_card.is_empty() and can_pair(selected_card, ref)
	var card_part = joins or not placements(ref).is_empty()
	if not card_part and placements("", ref).is_empty():
		return "unrelated"
	if card_part and ref in [selected_card, selected_partner]:
		clear_pick("partner" if ref == selected_partner else "card")
		return "changed"
	if not card_part and ref == selected_space:
		clear_pick("space")
		return "changed"
	var card = selected_card
	var space = selected_space
	var partner = selected_partner
	if not card_part:
		space = ref
	elif joins:
		partner = ref
	else:
		card = ref
		partner = ""
	if placements(card, space, partner).is_empty():
		return "blocked"
	selected_card = card
	selected_space = space
	selected_partner = partner
	return "changed"


func picked_ref(ref: String) -> bool:
	return ref in [selected_card, selected_partner, selected_space] or _contains_ref(held_action().get("arguments", {}), ref)


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
		if action.get("action_id") == "agent_turn":
			var args = action.arguments
			if not selected_space.is_empty() and args.get("space_id") != selected_space:
				continue
			if not selected_partner.is_empty():
				if not args.get("graft", false) or args.get("card_id") not in [selected_card, selected_partner]:
					continue
			elif not selected_card.is_empty() and args.get("card_id") != selected_card:
				continue
		_collect_refs(action.get("arguments", {}), result)
	return result


func _collect_refs(value: Variant, refs: Dictionary) -> void:
	if value is String:
		refs[value] = true
	elif value is Dictionary:
		_collect_refs(value.values(), refs)
	elif value is Array:
		for part in value:
			_collect_refs(part, refs)


func paid_cost(action: Dictionary) -> Dictionary:
	var args = action.get("arguments", {})
	var options = entry(str(args.get("space_id", ""))).get("options", [])
	var index = int(args.get("cost_option", 0))
	var cost: Dictionary = options[index].get("cost", {}).duplicate() if index >= 0 and index < options.size() else {}
	var discount = args.get("discount", "")
	if int(cost.get(discount, 0)) > 0:
		cost[discount] -= 1
	return cost


func cost_text(cost: Dictionary) -> String:
	var parts: PackedStringArray = []
	for key in ["solari", "spice", "water"]:
		var amount = int(cost.get(key, 0))
		if amount:
			parts.append("%s %d" % [phrase("{" + key + "}"), amount])
	return " · ".join(parts)


func known_deck_top() -> Dictionary:
	var private = view().get("private", {})
	var ref = str(private.get("peeked_card_id", ""))
	if ref.is_empty() or ref not in private.get("deck_cards", []):
		return {}
	var players = view().get("players", [])
	var glowglobes = active_seat >= 0 and active_seat < players.size() and "glowglobes" in players[active_seat].get("tech_ids", [])
	var source = catalog.get("tech" if glowglobes else "intrigue", {}).get("glowglobes" if glowglobes else "twisted_controlled", {})
	return {"ref": ref, "source": str(localized(source, "name"))}


func top_choice_card() -> String:
	if not actions().any(func(action): return DECK_TOP_CHOICES.has(action.action_id)):
		return ""
	return str(view().get("private", {}).get("peeked_card_id", ""))


func live_description(action: Dictionary) -> String:
	var top = top_choice_card()
	if not top.is_empty() and DECK_TOP_CHOICES.has(action.action_id):
		var notes = action_notes(action)
		return ui(DECK_TOP_CHOICES[action.action_id], {"card": name_of(top)}) + ("\n" + " · ".join(notes) if not notes.is_empty() else "")
	return describe(action)


func pile_groups(refs: Array, top = "") -> Array:
	var groups: Dictionary = {}
	for ref in refs:
		var key = ":".join(section_id(str(ref)))
		if not groups.has(key):
			groups[key] = []
		groups[key].append(str(ref))
	var sorted: Array = []
	for cards in groups.values():
		cards.sort()
		sorted.append(cards)
	sorted.sort_custom(func(a, b):
		var comparison = name_of(a[0]).naturalnocasecmp_to(name_of(b[0]))
		return a[0] < b[0] if comparison == 0 else comparison < 0
	)
	var result: Array = []
	for cards in sorted:
		if not top.is_empty() and top in cards:
			result.append({"ref": top, "count": 1, "top": true})
			cards.erase(top)
		if not cards.is_empty():
			result.append({"ref": cards[0], "count": cards.size(), "top": false})
	return result


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
		if key == "discount" and args.has("cost_option") and args.has("space_id"):
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
			var paid = cost_text(paid_cost(action))
			if paid.is_empty():
				paid = ui("render.free")
			if args.has("discount"):
				paid = native("인쇄 비용: ") + cost_text(options[index].get("cost", {})) + " → " + native("지불 비용: ") + paid + " (" + phrase("{" + str(args.discount) + ":1}") + ui("turn.discount_suffix") + ")"
			parts.append(paid + " → " + phrase(localized(options[index], "effect")))
	parts.append_array(action_notes(action))
	return heading + ("\n" + " · ".join(parts) if not parts.is_empty() else "")


func action_notes(action: Dictionary) -> PackedStringArray:
	var parts: PackedStringArray = []
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
	return parts


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
