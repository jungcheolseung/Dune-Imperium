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
	if failures.is_empty():
		print("GODOT_MODEL_TESTS_OK")
		quit(0)
	else:
		for failure in failures:
			push_error(failure)
		quit(1)
