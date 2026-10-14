extends SceneTree

const Model = preload("res://model.gd")
var failures: Array[String] = []


func check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _initialize() -> void:
	var model = Model.new()
	model.words = {"terms": {"spice": {"ko": "스파이스", "en": "spice"}}, "ko": {"ACTION_LABELS": {"take": "선택"}}}
	model.catalog = {"cards": {"dagger": {"name": "Dagger", "name_ko": "단검"}}, "intrigue": {"plot": {"name": "Plot", "name_ko": "책략"}}}
	check(model.name_of("player:0:starter:dagger:1") == "단검", "starter copy name")
	check(model.name_of("intrigue:plot:2") == "책략", "intrigue section")
	check(model.phrase("{spice:2}") == "스파이스 2", "reviewed term and count")
	check(model.localized({"detail": "available English", "detail_ko": null}, "detail") == "available English", "null Korean detail falls back to supplied English")
	var actions = [
		{"index": 2, "action_id": "agent_turn", "arguments": {"card_id": "player:0:starter:dagger:0", "space_id": "a"}},
		{"index": 3, "action_id": "agent_turn", "arguments": {"card_id": "player:0:starter:dagger:1", "space_id": "b"}},
		{"index": 4, "action_id": "take", "arguments": {}, "sent_by_turn_end": true},
	]
	model.adopt({"summary": {"game_id": "game", "revision": 5, "undo_count": 0}, "actions": {"actions": actions}})
	check(model.placements("player:0:starter:dagger:0").size() == 1, "copies never share a selection")
	model.selected_card = "player:0:starter:dagger:0"
	check(model.legal_refs().has("a") and not model.legal_refs().has("b"), "selected card limits targets")
	model.hold(actions[2])
	check(not model.held_action().is_empty(), "hold without sending")
	model.adopt({"summary": {"game_id": "game", "revision": 5, "undo_count": 1}, "actions": {"actions": actions}})
	check(model.held_action().is_empty(), "undo invalidates held index at equal revision")
	check(model.selected_card.is_empty(), "new generation drops selection")
	model.hold(actions[2])
	model.adopt({"summary": {"game_id": "another", "revision": 5, "undo_count": 1}, "actions": {"actions": actions}})
	check(model.held_action().is_empty(), "another game invalidates held index")
	check(model.request_body(actions[0]).undo_count == 1, "action carries undo generation")
	var text = model.describe({"action_id": "take", "arguments": {"effect_key": "internal_rule_key"}, "detail_ko": "{spice:2}"})
	check(text.contains("스파이스 2") and not text.contains("internal_rule_key") and not text.contains("{spice"), "detail is readable, internal effect key absent")
	var numeric = model.describe({"action_id": "deploy_troops", "arguments": {"count": 3.0, "player": 2.0, "destroy_shield_wall": true}})
	check(numeric.contains("3") and numeric.contains("앱 AI 2"), "JSON float counts and target seats remain distinguishable")
	model.catalog.intrigue.plot.text_ko = ["교전 — 효과 하나", "교전 — 효과 둘"]
	var option = model.describe({"action_id": "play_intrigue", "arguments": {"card_id": "intrigue:plot:0", "option": 1.0}})
	check(option.contains("효과 둘") and not option.contains("효과 하나"), "intrigue options show their printed effect")
	var data = {"summary": {"game_id": "same", "revision": 3, "undo_count": 0, "confirmation": null, "clock": {"elapsed": 1}}, "actions": {"actions": []}}
	model.adopt(data)
	var confirming = data.duplicate(true)
	confirming.summary.confirmation = 0
	check(model.adopt(confirming), "confirmation updates controls without a new revision")
	var clock_only = confirming.duplicate(true)
	clock_only.summary.clock.elapsed = 2
	check(not model.adopt(clock_only), "clock polling does not recreate action controls")
	var saved = {"seats": ["human", "app_ai", "app_ai", "app_ai"], "ruleset": {"players": 4, "leader_draft": true}}
	check(model.supported_save(saved), "basic drafted game can resume")
	var expanded = saved.duplicate(true)
	expanded.ruleset.bloodlines = true
	check(model.supported_save(expanded), "expansion saves can resume")
	var other_seat = saved.duplicate(true)
	other_seat.seats = ["app_ai", "human", "app_ai", "app_ai"]
	check(model.supported_save(other_seat), "a different human seat can resume")
	model.adopt({"summary": {"game_id": "end", "revision": 8}, "actions": {"actions": [{"index": 4, "action_id": "pass_combat_intrigue", "arguments": {}}]}})
	check(model.finish_action().action_id == "pass_combat_intrigue", "combat pass remains available on the finish control")
	var roles = {"you": {"seats": [1, 3]}, "summary": {"game_id": "roles", "revision": 2, "confirmation": 3, "decision": {"owner": 1}}, "view": {"player": 3}, "actions": {"actions": actions}}
	roles = JSON.parse_string(JSON.stringify(roles))
	check(model.pick_seat(roles) == 3, "confirmation takes precedence over a new hotseat decision")
	model.adopt(roles)
	check(model.active_seat == 3 and model.request_body(actions[0]).seat == 3, "requests carry the observed seat, never a fixed first seat")
	model.hold(actions[2])
	var switched = roles.duplicate(true)
	switched.view.player = 1
	model.adopt(switched)
	check(model.held_action().is_empty(), "switching perspective invalidates a held action")
	model.adopt({"summary": roles.summary, "you": {"seats": []}})
	check(model.active_seat == -1 and model.view().is_empty() and model.actions().is_empty(), "losing a seat clears private cards and controls")
	var clock = {"elapsed_ms": 5000, "seat_ms": [0, 0, 0, 0], "running": 0, "spell_ms": 100, "narration": [[1, 600], [2, 400]], "counting": true}
	var reading = model.clock_reading(clock, 1500)
	check(reading.elapsed == 6500 and reading.seats == [500.0, 600.0, 400.0, 0] and reading.spell == 600, "clock charges AI narration before the human, using server age")
	check(clock.seat_ms == [0, 0, 0, 0] and model.clock_text(3661000) == "1:01:01", "clock display never mutates the received totals")
	var jar = load("res://cookie_jar.gd").new()
	jar.remember("https://one", "dune_seat_g_1=private; Path=/games/g; Max-Age=10; HttpOnly; Secure", 100)
	check(jar.header("https://one", "/games/g/snapshot", 101).contains("private"), "owned game sends its cookie")
	check(jar.header("https://two", "/games/g", 101).is_empty() and jar.header("https://one", "/games/g2", 101).is_empty(), "cookies never cross origin or a game path boundary")
	check(jar.header("https://one", "/games/g", 111).is_empty(), "expired seat cookies are excluded")
	jar.remember("https://one", "dune_seat_g_1=; Path=/games/g; Max-Age=0", 101)
	check(jar.entries.is_empty(), "a release deletes the stored cookie")
	var timeline = [{"type": "action", "index": 0}, {"type": "action", "index": 1, "undone": true}, {"type": "undo", "index": 2}, {"type": "chance", "index": 3}, {"type": "action", "index": 4}]
	check(model.reviewed_log({"log": timeline}, 1).size() == 1 and model.reviewed_log({"log": timeline}, 2).size() == 4, "review log ends at its live cursor while retaining earlier undo history")
	if failures.is_empty():
		print("GODOT_MODEL_TESTS_OK")
		quit(0)
	else:
		for failure in failures:
			push_error(failure)
		quit(1)
