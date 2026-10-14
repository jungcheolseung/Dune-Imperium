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
	model.catalog.contracts = {"espionage|copy2": {"name": "Espionage", "name_ko": "첩보", "image": "/contract-image"}, "deliver_supplies": {"name_ko": "계약"}}
	model.catalog.spaces = {"deliver_supplies": {"name_ko": "보드 칸"}}
	check(model.name_of("contract:espionage|copy2") == "첩보" and model.entry("contract:espionage|copy2").image == "/contract-image", "physical contract IDs resolve their printed name and picture without dropping the copy suffix")
	check(model.name_of("contract:deliver_supplies") == "계약" and model.name_of("deliver_supplies") == "보드 칸", "contract and board-space identities remain distinct")
	var Expansions = preload("res://expansions.gd")
	check(not Expansions.scouts_visible(true, false, false, false) and Expansions.scouts_visible(true, true, false, false) and Expansions.scouts_visible(true, false, false, true) and not Expansions.scouts_visible(true, true, true, false), "Scouts opens for its decision or explicit browsing and does not cover the board during ordinary play")
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
	test_private_deck()
	test_quantities()
	test_choice_zones()
	if failures.is_empty():
		print("GODOT_MODEL_TESTS_OK")
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
	var rows = [
		{"index": 0, "action_id": "agent_turn", "arguments": {"card_id": first, "space_id": "a", "graft": true}},
		{"index": 1, "action_id": "agent_turn", "arguments": {"space_id": "a", "graft": true, "card_id": second}},
		{"index": 2, "action_id": "agent_turn", "arguments": {"card_id": second, "space_id": "b", "graft": true}},
		{"index": 3, "action_id": "agent_turn", "arguments": {"card_id": invalid, "space_id": "b"}},
	]
	model.adopt({"summary": {"game_id": "picks", "revision": 0}, "view": {"player": 0, "private": {"hand": [first, second, invalid]}}, "actions": {"actions": rows}})
	check(model.pick_step("a") == "changed" and model.legal_refs().has(first) and not model.legal_refs().has(invalid), "space-first lights only matching physical cards")
	check(model.pick_step(invalid) == "blocked" and model.selected_space == "a" and model.selected_card.is_empty(), "an invalid replacement preserves the selected space")
	model.pick_step(first)
	model.pick_step(second)
	check(model.selected_card == first and model.selected_partner == second, "picking a graft card joins rather than replaces the first card")
	check(model.picked_placements().size() == 1 and int(model.picked_placements()[0].index) == 0, "symmetric graft DTOs deduplicate and prefer the first card despite argument order")
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
