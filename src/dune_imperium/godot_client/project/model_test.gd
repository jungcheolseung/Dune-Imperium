extends SceneTree

const Model = preload("res://model.gd")
var failures: Array[String] = []
var checks = 0


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)


# A server payload of whole placements (codec v150): one card pick per card
# and graft, numbered from `first`, and `agent_placements` listing every
# placement each pick leads to; `others` follow the card picks.
func staged(placements: Array, others: Array = [], first = 0) -> Dictionary:
	var rows: Array = []
	var picks: Dictionary = {}
	var listed: Array = []
	for args in placements:
		var key = JSON.stringify([args.card_id, args.get("graft", false)])
		if not picks.has(key):
			var chosen = {"card_id": args.card_id}
			if args.get("graft", false):
				chosen.graft = true
			picks[key] = first + rows.size()
			rows.append({"index": picks[key], "action_id": "choose_agent_card", "arguments": chosen})
		listed.append({"index": picks[key], "placement": listed.size(), "arguments": args})
	rows.append_array(others)
	return {"actions": rows, "agent_placements": listed}


func _initialize() -> void:
	var model = Model.new()
	model.words = {"terms": {"spice": {"ko": "스파이스", "en": "spice"}}, "ko": {"ACTION_LABELS": {"take": "선택"}}}
	model.catalog = {"cards": {"dagger": {"name": "Dagger", "name_ko": "단검"}}, "intrigue": {"plot": {"name": "Plot", "name_ko": "책략"}}}
	check(model.name_of("player:0:starter:dagger:1") == "단검", "starter copy name")
	check(model.name_of("intrigue:plot:2") == "책략", "intrigue section")
	model.catalog.contracts = {"espionage|copy2": {"name": "Espionage", "name_ko": "첩보", "image": "/contract-image"}, "deliver_supplies": {"name_ko": "계약"}}
	model.catalog.spaces = {"deliver_supplies": {"name_ko": "보드 칸"}}
	check(model.name_of("contract:espionage|copy2") == "첩보" and model.entry("contract:espionage|copy2").image == "/contract-image", "physical contract IDs resolve their printed name and picture without dropping the copy suffix")
	check(model.name_of("contract:deliver_supplies") == "계약" and model.name_of("deliver_supplies") == "보드 칸", "contract and board-space identities remain distinct")
	var Expansions = preload("res://expansions.gd")
	check(not Expansions.scouts_visible(true, false, false, false) and Expansions.scouts_visible(true, true, false, false) and Expansions.scouts_visible(true, false, false, true) and not Expansions.scouts_visible(true, true, true, false), "Scouts opens for its decision or explicit browsing and does not cover the board during ordinary play")
	check(model.phrase("{spice:2}") == "스파이스 2", "reviewed term and count")
	check(model.localized({"detail": "available English", "detail_ko": null}, "detail") == "available English", "null Korean detail falls back to supplied English")
	var payload = staged([{"card_id": "player:0:starter:dagger:0", "space_id": "a"}, {"card_id": "player:0:starter:dagger:1", "space_id": "b"}], [{"index": 4, "action_id": "take", "arguments": {}, "sent_by_turn_end": true}], 2)
	var actions = payload.actions
	model.adopt({"summary": {"game_id": "game", "revision": 5, "undo_count": 0}, "actions": payload})
	check(model.placements("player:0:starter:dagger:0").size() == 1, "copies never share a selection")
	model.selected_card = "player:0:starter:dagger:0"
	check(model.legal_refs().has("a") and not model.legal_refs().has("b"), "selected card limits targets")
	model.hold(actions[2])
	check(not model.held_action().is_empty(), "hold without sending")
	model.adopt({"summary": {"game_id": "game", "revision": 5, "undo_count": 1}, "actions": payload})
	check(model.held_action().is_empty(), "undo invalidates held index at equal revision")
	check(model.selected_card.is_empty(), "new generation drops selection")
	model.hold(actions[2])
	model.adopt({"summary": {"game_id": "another", "revision": 5, "undo_count": 1}, "actions": payload})
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
	model.catalog.spaces = {"test_space": {"options": [{"effect": "base"}], "choam_options": [{"effect": "choam"}], "image_ko": "base-ko", "immortality": {"options": [{"effect": "specimens"}], "image": "tile"}}}
	model.adopt({"summary": {"game_id": "expanded", "revision": 1, "choam_module": true}})
	check(model.entry("test_space").options[0].effect == "choam", "space text uses the enabled CHOAM module")
	model.snapshot.summary.immortality = true
	check(model.entry("test_space").options[0].effect == "specimens" and not model.entry("test_space").has("image_ko"), "Immortality overrides the effective tile and removes the base-language image")
	check(model.catalog.spaces.test_space.options[0].effect == "base", "effective space presentation never mutates the catalog")
	var choice = {"index": 9, "action_id": "select_cards", "arguments": {"card_ids": ["imperium:dagger:1", "imperium:dagger:2"]}, "sent_by_turn_end": true}
	model.adopt({"summary": {"game_id": "expanded", "revision": 1}, "actions": {"actions": [choice], "unavailable": {"refs": {"tech": {"reason": "spice"}}}}})
	check(model.ref_actions("imperium:dagger:2").size() == 1 and model.ref_actions("imperium:dagger:3").is_empty(), "card arrays match exact physical references")
	check(model.unavailable("tech").reason == "spice" and model.unavailable("unknown").is_empty(), "disabled reasons come only from the server")
	model.hold(choice)
	var changed_choice = choice.duplicate(true)
	changed_choice.arguments.card_ids = ["imperium:dagger:3"]
	model.snapshot.actions.actions = [changed_choice]
	check(not model.offered(choice) and model.offered(changed_choice) and model.held_action().is_empty(), "same index and revision cannot send or confirm replaced arguments")
	model.language = "en"
	check(model.native("스파이스 비용 %d") % 3 == "Spice cost 3" and model.native("내 손패") == "My hand", "native English preserves costs and hand labels")
	model.language = "ko"
	model.words.prompt_patterns = [["^Pay (\\d+) Spice to gain (\\d+) Victory Point$", "{spice} $1 지불 → $2점"]]
	model.snapshot.summary.decision = {"prompt": "Pay 4 Spice to gain 2 Victory Point"}
	check(model.prompt() == "스파이스 4 지불 → 2점", "dynamic prompt uses the reviewed pattern and glossary")
	var Effects = preload("res://table_effects.gd")
	var earlier = {"summary": {"game_id": "effects", "revision": 2, "undo_count": 0}, "view": {"player": 0, "players": [{"player": 0, "victory_points": 1, "resources": {"spice": 2}}]}, "log": {"entries": []}}
	var later = earlier.duplicate(true)
	later.summary.revision = 3
	later.view.players[0].resources.spice = 5
	check(Effects.changes(earlier, later, false)[0].delta.spice == 3, "resource cue comes from public state differences")
	check(Effects.changes(earlier, later, true).is_empty(), "review cursor changes generate no live cue")
	later.summary.undo_count = 1
	check(Effects.changes(earlier, later, false).is_empty(), "undo produces no false acquisition or resource cue")
	test_staged_picks()
	test_two_step_placement()
	test_private_deck()
	test_quantities()
	test_choice_zones()
	test_choice_reading()
	test_feedback_context()
	test_reference_feedback()
	test_turn_reading()
	if failures.is_empty():
		print("GODOT_MODEL_TESTS_OK %d" % checks)
		quit(0)
	else:
		for failure in failures:
			push_error(failure)
		quit(1)


func test_staged_picks() -> void:
	var model = Model.new()
	var first = "imperium:ordinary:0"
	var second = "imperium:graft:0"
	var invalid = "imperium:ordinary:1"
	model.catalog = {"cards": {"ordinary": {}, "graft": {"graft": true}}, "spaces": {"a": {}, "b": {}}}
	var rows = staged([
		{"card_id": first, "space_id": "a", "graft": true},
		{"space_id": "a", "graft": true, "card_id": second},
		{"card_id": second, "space_id": "b", "graft": true},
		{"card_id": invalid, "space_id": "b"},
	])
	model.adopt({"summary": {"game_id": "picks", "revision": 0}, "view": {"player": 0, "private": {"hand": [first, second, invalid]}}, "actions": rows})
	check(model.placement_rows().size() == 4 and model.table_actions().size() == 4, "the card picks are reached only through their placements")
	check(model.offered(model.placements(second, "b")[0]) and not model.offered({"index": 1, "action_id": "agent_turn", "placement": 2, "arguments": {"card_id": second, "space_id": "a", "graft": true}}), "a placement is offered only with its own card pick, position and arguments")
	check(model.pick_step("a") == "changed" and model.legal_refs().has(first) and not model.legal_refs().has(invalid), "space-first lights only matching physical cards")
	check(model.pick_step(invalid) == "blocked" and model.selected_space == "a" and model.selected_card.is_empty(), "an invalid replacement preserves the selected space")
	model.pick_step(first)
	model.pick_step(second)
	check(model.selected_card == first and model.selected_partner == second, "picking a graft card joins rather than replaces the first card")
	check(model.picked_placements().size() == 1 and int(model.picked_placements()[0].pick_index) == 0, "symmetric graft DTOs deduplicate and prefer the first card despite argument order")
	check(model.legal_refs().has(first) and model.legal_refs().has(second), "both grafted cards stay lit even when the chooser deduplicates their moves")
	model.clear_pick("space")
	check(model.picked_placements().size() == 2 and model.legal_refs().has("a") and model.legal_refs().has("b"), "a graft pair reaches the union of both offered routes")
	model.clear_pick("card")
	check(model.selected_card == second and model.selected_partner.is_empty(), "removing the first card promotes its partner")
	model.pick_step(second)
	check(model.selected_card.is_empty(), "clicking a picked card cancels only its step")
	check(not model.can_pair(first, first) and not model.can_pair(first, "imperium:graft:99"), "a pair requires distinct cards in the authorized hand")
	model.selected_partner = second
	var newer = model.snapshot.duplicate(true)
	newer.summary.revision = 1
	model.adopt(newer)
	check(model.selected_partner.is_empty(), "a new revision clears both picked cards")
	var nested = {"index": 4, "action_id": "trash", "arguments": {"card_ids": [first]}, "sent_by_turn_end": true}
	model.snapshot.actions.actions = [nested]
	model.hold(nested)
	check(model.legal_refs().has(first) and model.picked_ref(first), "nested references light a held table object")
	model.catalog.spaces.a.options = [{"cost": {"spice": 1, "water": 2}}]
	var discounted = {"arguments": {"space_id": "a", "cost_option": 0, "discount": "spice"}}
	check(model.paid_cost(discounted) == {"spice": 0, "water": 2} and model.catalog.spaces.a.options[0].cost.spice == 1, "paid cost applies only the offered discount without changing printed catalog cost")


func test_two_step_placement() -> void:
	var model = Model.new()
	var card = "imperium:graft:0"
	model.catalog = {"cards": {"graft": {"graft": true}}, "spaces": {"a": {}, "b": {}}}
	# The server holds the card pick (a reload or an undo of the space pick):
	# its space picks become the placements, with the picked card.
	var held = {"summary": {"game_id": "held", "revision": 7, "undo_count": 0, "undo": [{"seat": 0, "steps": 2}]}, "view": {"player": 0, "private": {"hand": [], "agent_card_pick": card, "agent_card_pick_graft": true}},
		"actions": {"actions": [{"index": 0, "action_id": "place_agent", "arguments": {"space_id": "a"}}, {"index": 1, "action_id": "place_agent", "arguments": {"space_id": "b", "cost_option": 1}}], "agent_placements": null},
		"log": {"entries": [{"type": "action", "actor": 0, "action_id": "choose_agent_card", "undone": false}, {"type": "action", "actor": 0, "action_id": "place_agent", "pick": true, "undone": true}, {"type": "action", "actor": 1, "action_id": "place_agent", "undone": false}]}}
	model.adopt(JSON.parse_string(JSON.stringify(held)))
	var rows = model.placement_rows()
	check(rows.size() == 2 and rows[1].arguments == {"space_id": "b", "cost_option": 1.0, "card_id": card, "graft": true} and int(rows[1].index) == 1 and not rows[1].has("pick_index"), "a held card pick turns the space picks into whole placements")
	check(model.selected_card == card, "the held card is the staged card")
	model.clear_pick()
	check(model.selected_card == card, "only an undo returns a card the server holds")
	check(model.offered(rows[0]) and model.request_body(rows[0]).index == 0, "a held card's placement sends its own space pick")
	check(model.legal_refs().has("a") and model.legal_refs().has("b"), "the held card's spaces stay lit")
	check(model.undo_steps() == 1, "one undo takes one step unless the last two live steps are this seat's card and space picks")
	# After the card pick lands the matching space pick follows (followWithSpace).
	var placement = JSON.parse_string(JSON.stringify({"index": 5, "action_id": "agent_turn", "pick_index": 5, "placement": 0, "arguments": {"card_id": card, "graft": true, "space_id": "b", "cost_option": 1}}))
	check(int(model.space_pick_for(placement).get("index", -1)) == 1, "the space pick with the same space arguments follows the card pick")
	placement.arguments.graft = false
	check(model.space_pick_for(placement).is_empty(), "a space pick never follows a different card or graft")
	var placed = JSON.parse_string(JSON.stringify(held))
	placed.summary.revision = 8
	placed.view.private.agent_card_pick = null
	placed.actions = {"actions": [{"index": 0, "action_id": "finish_conflict_end_intrigue", "arguments": {}}]}
	placed.log.entries = [{"type": "action", "actor": 0, "action_id": "choose_agent_card", "undone": false}, {"type": "action", "actor": 0, "action_id": "place_agent", "undone": false}]
	model.adopt(placed)
	check(model.undo_steps() == 2, "a placement undoes as its card pick and its space pick")
	check(model.selected_card.is_empty() and model.placement_rows().is_empty(), "no placement once the card pick is spent")
	check(int(model.finish_action().get("index", -1)) == 0 and "resolve_scouts_choice_without_option" in Model.END_ACTIONS, "the server's newer explicit turn ends are the turn-end press")
	# A trash icon is told apart by what printed it, and reads by that name.
	model.snapshot.view.box_losing_trash = [{"action_id": "trash_optional_card", "card_id": "c", "source": "card", "printed": "imperium:graft:0", "printed_box": 1}]
	var trash = {"action_id": "trash_optional_card", "arguments": {"card_id": "c", "source": "card", "printed": "imperium:graft:0", "printed_box": 1}}
	check(model.loses_box(trash), "the printed icon's own trash loses its box")
	var other = trash.duplicate(true)
	other.arguments.printed_box = 2
	check(not model.loses_box(other), "another icon of the same card does not lose that box")
	model.words = {"ko": {"PAYLOAD_KEY_LABELS": {"source": "출처", "printed_box": "칸", "printed": "인쇄"}}}
	var text = model.describe({"action_id": "resolve_research_icon", "arguments": {"source": "research", "printed": "a", "printed_box": 3}, "detail_ko": "연구 칸"})
	check(not text.contains("출처") and not text.contains("칸:") and not text.contains("인쇄"), "a named printer hides its kind and box, and its name when the detail says it")
	# What this seat bought since its own last live Reveal began (boughtThisReveal).
	model.snapshot.log = {"entries": [
		{"type": "action", "actor": 0, "action_id": "reveal_turn", "undone": false, "events": []},
		{"type": "action", "actor": 0, "action_id": "acquire_imperium", "undone": false, "events": [{"kind": "card_acquired", "payload": {"player": 0.0, "card_id": "imperium:early:0"}}]},
		{"type": "action", "actor": 0, "action_id": "reveal_turn", "undone": false, "events": []},
		{"type": "action", "actor": 0, "action_id": "acquire_imperium", "undone": true, "events": [{"kind": "card_acquired", "payload": {"player": 0.0, "card_id": "imperium:undone:0"}}]},
		{"type": "action", "actor": 1, "action_id": "acquire_imperium", "undone": false, "events": [{"kind": "card_acquired", "payload": {"player": 1.0, "card_id": "imperium:other:0"}}]},
		{"type": "action", "actor": 0, "action_id": "acquire_reclaimed_forces", "undone": false, "events": [{"kind": "reclaimed_forces_acquired", "payload": {"player": 0.0}}]},
		{"type": "action", "actor": 0, "action_id": "acquire_tleilaxu", "undone": false, "events": [{"kind": "tleilaxu_card_acquired", "payload": {"player": 0.0, "card_id": "tleilaxu:row:0"}}]},
	]}
	check(model.bought_this_reveal() == ["reclaimed_forces", "tleilaxu:row:0"], "only this Reveal's live purchases of this seat are listed")
	test_turn_start_window()
	test_server_errors()
	test_table_objects()


func test_table_objects() -> void:
	var model = Model.new()
	var card = "imperium:dagger:0"
	model.catalog = {"spaces": {"a": {}}, "posts": {"post_a": [10, 10]}}
	var spy = {"index": 1, "action_id": "place_spy_on_space", "arguments": {"post_id": "post_a"}}
	var rows = staged([{"card_id": card, "space_id": "a", "infiltrate_post_id": "post_a"}], [spy])
	model.adopt({"summary": {"game_id": "objects", "revision": 1}, "view": {"player": 0, "private": {"hand": [card]}}, "actions": rows})
	check(model.ref_actions("post_a") == [spy] and model.spy_post_actions("post_a") == [spy], "a post answers its Spy destinations, never a placement that infiltrates through it")
	var bare = {"summary": {"game_id": "objects", "revision": 2}, "view": {"player": 0, "private": {"hand": [card]}}, "actions": {"actions": [{"index": 0, "action_id": "choose_agent_card", "arguments": {"card_id": card}}], "agent_placements": null}}
	model.adopt(bare)
	check(model.placement_rows().is_empty() and model.ref_actions(card).size() == 1 and model.legal_refs().has(card), "without listed placements the hand still reaches the raw card pick")


func test_server_errors() -> void:
	var model = Model.new()
	model.words = {"server_errors": {"exact": {"action index is out of range": "행동 번호가 범위를 벗어났습니다"}, "patterns": [["^unknown game: (.+)$", "알 수 없는 게임입니다: $1"], ["^save step (\\d+)\\b.*$", "저장 기록의 #1번째 수에 문제가 있습니다"]]}}
	check(model.server_error("action index is out of range") == "행동 번호가 범위를 벗어났습니다", "an exact server sentence reads in Korean")
	check(model.server_error("unknown game: abc") == "알 수 없는 게임입니다: abc", "a pattern keeps its group")
	check(model.server_error("save step 4 broke") == "저장 기록의 5번째 수에 문제가 있습니다", "#N names the engine's zero-based number as the visible one")
	check(model.server_error("something new") == "something new" and model.server_error({"code": 1}) == JSON.stringify({"code": 1}), "an unknown message stays as the server wrote it")
	model.language = "en"
	check(model.server_error("action index is out of range") == "action index is out of range", "the English table keeps the server's sentence")


func test_turn_start_window() -> void:
	var model = Model.new()
	var play = {"index": 2, "action_id": "play_intrigue", "arguments": {"card_id": "intrigue:withdrawn:0", "option": 0}, "turn_start": true}
	var rows = staged([{"card_id": "imperium:dagger:0", "space_id": "a"}], [play])
	rows.agent_boxes = [{"box": 1}]
	model.adopt({"summary": {"game_id": "start", "revision": 4, "undo_count": 0}, "view": {"player": 0, "private": {"hand": ["imperium:dagger:0"]}}, "actions": rows})
	check(model.turn_start_window_open() and model.actions() == [play], "a turn-start play is asked first and alone")
	check(model.placement_rows().is_empty() and model.payload().agent_boxes == null and not model.legal_refs().has("a"), "nothing else of the turn is offered while the window is up")
	model.keep_turn_start()
	check(not model.turn_start_window_open() and model.actions().size() == 2 and model.placement_rows().size() == 1, "putting the window aside brings the whole turn back, the play still in it")
	var later = model.snapshot.duplicate(true)
	later.summary.revision = 9
	model.adopt(later)
	check(model.turn_start_window_open(), "the seat's next turn asks again")
	for index in range(30):
		model.summary().revision = 100 + index
		model.keep_turn_start()
	check(model.turn_start_kept.size() == Model.TURN_START_KEPT_LIMIT and model.turn_start_kept[-1] == "start:0:129", "only the latest turns put aside are remembered")


func test_private_deck() -> void:
	var model = Model.new()
	model.catalog = {"cards": {"dagger": {"name": "Dagger"}, "ring": {"name": "Ring"}}, "tech": {"glowglobes": {"name": "Glowglobes"}}, "intrigue": {"twisted_controlled": {"name": "Controlled"}}}
	model.language = "en"
	model.words.ui = {"panels.deck_top_discard": {"en": "Discard ({{card}})"}}
	var top = "imperium:dagger:2"
	var other = "imperium:dagger:1"
	var ring = "imperium:ring:1"
	model.adopt({"summary": {"game_id": "deck", "revision": 1}, "view": {"player": 0, "players": [{"tech_ids": ["glowglobes"]}], "private": {"peeked_card_id": top, "deck_cards": [ring, other, top]}}, "actions": {"actions": [{"index": 1, "action_id": "discard_top_card", "arguments": {}}]}})
	check(model.known_deck_top() == {"ref": top, "source": "Glowglobes"}, "only the authorized deck member receives its typed effect source")
	var grouped = model.pile_groups([ring, top, other], top)
	check(grouped[0] == {"ref": top, "count": 1, "top": true} and grouped[1] == {"ref": other, "count": 1, "top": false}, "the known physical top copy splits off before its remaining copies")
	check(grouped == model.pile_groups([other, ring, top], top), "no order below the known top affects the displayed deck")
	check(model.live_description(model.actions()[0]) == "Discard (Dagger)" and not model.describe(model.actions()[0]).contains("Dagger"), "only the live choice names the private top, never a shared log description")
	model.snapshot.view.players[0].tech_ids = []
	check(model.known_deck_top().source == "Controlled", "the deck note names Controlled when Glowglobes is absent")
	model.snapshot.actions = null
	check(model.top_choice_card().is_empty(), "readonly views never manufacture a live private choice")
	model.snapshot.view.private.peeked_card_id = "imperium:dagger:99"
	check(model.known_deck_top().is_empty(), "a stale peek outside the current deck is never marked")
	check(model.pile_groups([other, top]).size() == 1 and int(model.pile_groups([other, top])[0].count) == 2, "an unknown top keeps all equivalent copies grouped")


func test_quantities() -> void:
	var model = Model.new()
	var deploy = [
		{"index": 4, "action_id": "deploy_troops", "arguments": {"count": 2}},
		{"index": 3, "action_id": "deploy_troops", "arguments": {"count": 1}},
		{"index": 5, "action_id": "deploy_troops", "arguments": {"count": 3}},
	]
	model.adopt({"summary": {"game_id": "quantities", "revision": 1}, "view": {"player": 0, "private": {}}, "actions": {"actions": deploy}})
	check(int(model.selected_quantity(deploy).index) == 5, "sending units defaults to the largest legal quantity, independent of DTO order")
	check(model.stage_quantity(deploy[1]) and int(model.selected_quantity(deploy).index) == 3 and int(model.summary().revision) == 1, "staging changes only the local selected legal quantity")
	var clock = model.snapshot.duplicate(true)
	clock.summary.clock = {"elapsed_ms": 2}
	model.adopt(clock)
	check(int(model.selected_quantity(deploy).index) == 3, "an unrelated clock render retains the staged amount")
	var newer = model.snapshot.duplicate(true)
	newer.summary.revision = 2
	model.adopt(newer)
	check(model.local_counts.is_empty() and int(model.selected_quantity(deploy).index) == 5, "a new engine generation cannot reuse a previous amount")
	var one = {"action_id": "deploy_troops", "arguments": {"count": 1, "box": 0}}
	var other = {"action_id": "deploy_troops", "arguments": {"box": 1, "count": 1}}
	check(model.quantity_key(one, "count") != model.quantity_key(other, "count"), "independent effect boxes never share a quantity")
	var bids = [
		{"index": 0, "action_id": "scouts_bid", "arguments": {"count": 0}},
		{"index": 1, "action_id": "scouts_bid", "arguments": {"count": 1}},
		{"index": 2, "action_id": "scouts_bid", "arguments": {"count": 2}},
	]
	model.snapshot.actions.actions = bids
	model.snapshot.view.private.scouts_bid = 2
	check(int(model.selected_quantity(bids).index) == 2, "a sealed auction starts at its own recorded bid")
	model.snapshot.view.private.scouts_bid = -1
	check(int(model.selected_quantity(bids).index) == 0, "an unrecorded sealed bid starts at zero")
	check(not model.stage_quantity({"index": 99, "action_id": "scouts_bid", "arguments": {"count": 99}}), "an unoffered quantity cannot be staged")
	var held = deploy[0].duplicate(true)
	held.sent_by_turn_end = true
	model.snapshot.actions.actions = [held, deploy[1]]
	model.hold(held)
	model.stage_quantity(deploy[1])
	check(model.held_action().is_empty(), "changing a held quantity clears the old hold without sending or replacing it")
	var calls = [{"index": 8, "action_id": "scouts_call", "arguments": {"count": 0}}, {"index": 9, "action_id": "scouts_call", "arguments": {"count": 1}}]
	model.snapshot.actions.actions = calls
	model.stage_quantity(calls[1])
	check(int(model.finish_action().index) == 9, "the open call uses the staged DTO as the single turn-end action")


func test_choice_zones() -> void:
	var model = Model.new()
	var refs = ["player:1:starter:dagger:0", "imperium:dagger:1", "reserve:dagger:2", "imperium:dagger:3"]
	var rows: Array = []
	for index in range(refs.size()):
		rows.append({"index": index, "action_id": "trash_optional_card", "arguments": {"card_id": refs[index]}})
	rows.append({"index": 4, "action_id": "trash_grafted_card_for_influence", "arguments": {}})
	model.adopt({"summary": {"game_id": "zones", "revision": 1}, "view": {"player": 1, "private": {"hand": [refs[0]]}, "players": [{"player": 1, "discard_pile": [refs[1]], "in_play": [refs[2], refs[3]]}], "turn_card_ids": [refs[2]], "box_losing_trash": [{"action_id": "trash_optional_card", "card_id": refs[2]}, {"action_id": "trash_grafted_card_for_influence"}]}, "actions": {"actions": rows}})
	check(model.own_card_zone(refs[0]) == "hand" and model.own_card_zone(refs[1]) == "discard_pile", "physical copies use the viewing seat's actual hand and discard zones")
	check(model.own_card_zone("imperium:dagger:8").is_empty(), "unowned and unseen cards have no personal zone")
	var zones = model.choice_zones(rows)
	check(zones == {0: "hand", 1: "discard_pile", 2: "turn_pending", 3: "earlier_turn", 4: "turn_pending"}, "current-turn, earlier-turn and card-less graft trash warnings come from the server dry run")
	model.snapshot.view.pending_box_card_ids = [refs[2]]
	model.snapshot.view.box_losing_trash = []
	check(model.choice_zones(rows)[2] == "turn", "a pending box alone never invents a lost-box warning for a self-trash")
	model.snapshot.view.turn_card_ids = []
	check(model.choice_zones([rows[2], rows[3]]).is_empty(), "same-pile interchangeable copies do not gain misleading suffixes")
	model.snapshot.view.private.hand = []
	model.snapshot.view.players = [{"player": 0, "in_play": [refs[2]], "discard_pile": [refs[1]]}]
	check(model.choice_zones(rows).is_empty(), "another seat's public cards are not classified as our personal piles")
	model.catalog = {"cards": {"dagger": {"name": "Dagger"}}, "spaces": {"a": {"name": "A"}}}
	var pair = {"index": 5, "action_id": "agent_turn", "arguments": {"space_id": "a", "card_id": refs[0], "cards": [refs[0], refs[1]], "effect_key": "unrecognized"}}
	check(model.preview_refs(pair) == ["a", refs[0], refs[1]], "effect previews include all known references once, including nested card arrays")
	model.snapshot.actions.agent_boxes = [{"box": 1, "card_id": refs[0]}]
	var box = {"index": 6, "action_id": "resolve_agent_card_effect", "box": 1, "arguments": {}}
	check(model.preview_refs(box) == [refs[0]], "an argument-less Agent box can inspect the server-named card")
	model.snapshot.actions.agent_boxes = null
	check(model.preview_refs(pair) == ["a", refs[0], refs[1]], "server null boxes leave ordinary effect previews available")
	check(model.describe(rows[2]) == model.live_description(rows[2]), "personal zone warnings stay out of the shared log description")


func test_choice_reading() -> void:
	var model = Model.new()
	model.words = {"terms": {"spice": {"ko": "스파이스", "en": "Spice"}}, "ko": {"ACTION_LABELS": {"take": "선택"}}, "ui": {"render.free": {"ko": "무료", "en": "Free"}, "render.irreversible_badge": {"ko": "되돌리기 불가", "en": "Cannot undo"}, "render.turn_card_pending_suffix": {"ko": "이번 턴 · 남은 효과 소실", "en": "This turn · Lose remaining effects"}}}
	model.catalog = {"spaces": {"a": {"options": [{"cost": {"spice": 3}, "effect": "first effect"}, {"cost": {"spice": 1}, "effect": "chosen effect"}]}}}
	var action = {"index": 9, "action_id": "take", "arguments": {"space_id": "a", "cost_option": 1, "discount": "spice"}, "strength_after": 5, "undoable": false}
	for language in ["ko", "en"]:
		model.language = language
		var reading = model.choice_reading(action, "", "turn_pending")
		check(reading.payment.begins_with(model.native("지불 비용: ") + model.ui("render.free")) and reading.payment.contains(model.native("인쇄 비용: ") + model.cost_text({"spice": 1})), "payment separates the discounted free amount from its printed cost in " + language)
		check(reading.effect == "chosen effect" and not reading.context.contains("chosen effect"), "only the selected option's effect gets a separate reading line in " + language)
		check(reading.previews.size() == 1 and reading.warnings.size() == 2 and reading.zone.is_empty(), "preview, irreversibility and the server-named lost-box warning stay distinct in " + language)
		check(not reading.context.contains(" → 5") and not reading.context.contains(model.ui("render.irreversible_badge")), "annotations do not repeat in the action context in " + language)
		var plain = model.choice_reading({"action_id": "take", "arguments": {}}, "Scouts supplied wording")
		check(plain.title == "Scouts supplied wording" and plain.payment.is_empty() and plain.effect.is_empty(), "a server-supplied Scouts description is retained without invented costs in " + language)
	model.language = "ko"
	check(model.describe({"action_id": "take", "arguments": {}, "detail": "{spice:2}", "strength_after": 5, "undoable": false}) == "선택\n스파이스 2 · 전투력 → 5 · 되돌리기 불가", "public log formatting stays identical when live hints are separated")
	var warned = model.choice_reading({"action_id": "take", "arguments": {}, "warning": "server warning", "reveal_preview": {"persuasion": 3, "strength": 4}})
	check(warned.previews.size() == 1 and warned.warnings == PackedStringArray(["server warning"]), "reveal preview and the supplied warning occupy separate categories")


func test_feedback_context() -> void:
	var Feedback = preload("res://action_feedback.gd")
	var context = {"game": "receipt", "seat": 0, "revision": 4, "undo": 0}
	var snapshot = {"summary": {"game_id": "receipt", "revision": 4, "undo_count": 0}, "view": {"player": 0}, "you": {"seats": [0]}}
	snapshot = JSON.parse_string(JSON.stringify(snapshot))
	check(Feedback.current(context, snapshot, false) and not Feedback.confirmed(context, snapshot, false), "a local choice without an advanced server snapshot is never an applied receipt")
	snapshot.summary.revision = 5
	check(Feedback.confirmed(context, snapshot, false), "a same-seat advanced snapshot can confirm an accepted action")
	check(not Feedback.confirmed(context, snapshot, true), "review never displays a live applied receipt")
	for change in ["game", "seat", "ownership", "undo", "revision"]:
		var invalid = snapshot.duplicate(true)
		match change:
			"game": invalid.summary.game_id = "other"
			"seat": invalid.view.player = 1
			"ownership": invalid.you.seats = []
			"undo": invalid.summary.undo_count = 1
			"revision": invalid.summary.revision = 3
		check(not Feedback.current(context, invalid, false), "receipt is cleared by changed " + change)


func test_reference_feedback() -> void:
	var model = Model.new()
	var first = "imperium:ordinary:0"
	var other = "imperium:other:0"
	var graft = "imperium:graft:0"
	model.catalog = {"cards": {"ordinary": {"name": "First"}, "other": {"name": "Other"}, "graft": {"name": "Graft", "graft": true}}, "spaces": {"a": {"name": "A"}, "b": {"name": "B"}, "c": {"name": "C"}}, "post_spaces": {"post_a": ["a", "b"]}}
	var rows = staged([{"card_id": first, "space_id": "a"}, {"card_id": other, "space_id": "b"}, {"card_id": graft, "space_id": "b", "graft": true}])
	rows.unavailable = {"refs": {"blocked": {"reason": "server reason", "reason_ko": "서버 이유"}}}
	model.adopt(JSON.parse_string(JSON.stringify({"summary": {"game_id": "pointer", "revision": 1}, "view": {"player": 0, "private": {"hand": [first, other, graft]}}, "actions": rows})))
	check(model.ref_feedback(first).kind == "available" and model.ref_feedback("a").kind == "available", "offered cards and spaces share the same available state")
	check(model.ref_feedback("c").kind == "inspect" and model.ref_feedback("c").hint.is_empty(), "an absent legal action never invents an unavailable reason")
	check(model.pick_step(first) == "changed" and model.ref_feedback(first).kind == "selected", "staged card selection is distinct from availability")
	check(model.ref_feedback(first).hint == model.native("다시 누르면 선택을 해제합니다."), "only staged picks advertise deselection by a second click")
	check(model.ref_feedback("b").kind == "filtered" and model.ref_feedback(other).kind == "filtered", "current card constraints mark incompatible offered targets as filtered, not server-forbidden")
	check(model.ref_feedback("b").hint == model.native("현재 고른 카드·칸과 함께 사용할 수 없습니다."), "filtered guidance describes the existing local choice constraint")
	check(model.ref_feedback(graft).kind == "partner", "an offered graft pairing has its own state")
	model.selected_space = "a"
	check(model.ref_feedback(graft).kind == "filtered", "a pairing absent from the selected space is not advertised as selectable")
	model.clear_pick()
	model.snapshot.actions.unavailable.refs[first] = {"reason": "a different option is unavailable"}
	check(model.ref_feedback(first).kind == "available", "an actual offered action takes precedence over an unavailable alternate option")
	for language in ["ko", "en"]:
		model.language = language
		check(model.ref_feedback("blocked").kind == "unavailable" and model.ref_feedback("blocked").hint == ("서버 이유" if language == "ko" else "server reason"), "unavailable guidance uses only the localized server reason in " + language)
		check(model.ref_feedback("post_a").name == model.native("관측소 · ") + "A / B", "post guidance uses its visible board names in " + language)
	var before = JSON.stringify(model.snapshot)
	model.ref_feedback("b")
	check(JSON.stringify(model.snapshot) == before and model.selected_card.is_empty(), "reading pointer guidance never changes the snapshot or stages a pick")
	var held = {"index": 3, "action_id": "select_cards", "arguments": {"card_ids": [first]}, "sent_by_turn_end": true}
	model.snapshot.actions.actions = [held]
	model.hold(held)
	check(model.ref_feedback(first).kind == "selected" and model.ref_feedback(first).hint == model.native("턴 종료로 선택을 확정합니다."), "a held table choice advertises turn-end confirmation, never false deselection")
	model.adopt({"summary": {"game_id": "pointer", "revision": 2}, "view": {"player": 1}, "you": {"seats": []}, "actions": null})
	check(model.ref_feedback(first).kind == "inspect" and model.ref_feedback(first).hint.is_empty(), "a changed readonly seat retains no private selection guidance")


func test_turn_reading() -> void:
	var model = Model.new()
	model.adopt(JSON.parse_string(JSON.stringify({"summary": {"game_id": "turn", "revision": 0, "decision": {"owner": 0}}, "view": {"player": 2}, "you": {"seats": [2]}})))
	check(model.turn_reading().seat == 0 and model.turn_reading().kind == "decision", "public decision owner is normalized from JSON, independently of the viewed seat")
	model.snapshot.summary.thinking = 1.0
	check(model.turn_reading().seat == 1 and model.turn_reading().kind == "thinking", "the public thinking seat is distinguished from a pending decision")
	model.snapshot.summary.thinking = null
	model.snapshot.summary.decision = null
	model.snapshot.summary.confirmation = 3.0
	check(model.turn_reading().seat == 3 and model.turn_reading().kind == "confirmation", "a server confirmation remains visible even without a decision")
	for language in ["ko", "en"]:
		model.language = language
		check(model.turn_reading().label == ("확정 대기" if language == "ko" else "Confirm"), "confirmation chrome is localized in " + language)
	model.snapshot.summary.finished = true
	check(model.turn_reading().kind == "finished" and model.turn_reading().seat == -1, "a finished game does not highlight a stale live owner")
	check(model.turn_reading(true).kind == "review" and model.turn_reading(true).seat == -1, "review never misrepresents retained live finished/decision fields as historical turn data")
	model.snapshot.summary.finished = false
	model.snapshot.summary.confirmation = null
	check(model.turn_reading().kind == "idle" and model.turn_reading().seat == -1, "an absent public owner invents no active seat")
	model.snapshot.summary.decision = {"owner": 9}
	check(model.turn_reading().seat == -1, "an invalid public seat never indexes the seat palette")
	var before = JSON.stringify(model.snapshot)
	model.turn_reading()
	check(before == JSON.stringify(model.snapshot) and model.active_seat == 2 and model.actions().is_empty(), "turn presentation cannot change the snapshot, view or legal choices")
	model.owned_seats = [1, 2]
	check(model.seat_marker(2) == "owned" and model.seat_marker(1).is_empty(), "a local multi-human table marks only the viewed seat as You")
	model.server_info.access = "remote"
	check(model.seat_marker(1) == "owned" and model.seat_marker(2) == "owned", "a remote table identifies every actually claimed seat")
	check(model.seat_marker(2, true) == "viewing" and model.seat_marker(1, true).is_empty(), "review distinguishes the viewing perspective from live seat ownership")
	model.owned_seats.clear()
	check(model.seat_marker(2) == "viewing", "a readonly perspective is not labelled as an owned seat")
	model.snapshot.summary.seats = ["human", "app_ai", "human", "app_ai"]
	model.words = {"ui": {"common.seat": {"ko": "플레이어{{seat}}", "en": "Player {{seat}}"}}}
	check(model.seat_name(2) == "Player 2", "viewing another human never renames that person You")
	model.active_seat = 1
	check(model.seat_name(1) == "AI 1", "an AI-only review does not rename its viewed AI You")
