extends VBoxContainer

# A quiet receipt in the history area. It never delays a choice or adds an
# animation, and is cleared when its authorized seat/generation is no longer live.
var table: Control
var receipt: Dictionary = {}
var heading: Label
var detail: Label


func setup(owner_table: Control, parent: Node) -> void:
	table = owner_table
	parent.add_child(self)
	add_theme_constant_override("separation", 3)
	heading = table._label(self, "", 13)
	heading.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	detail = table._label(self, "", 12)
	detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail.max_lines_visible = 2
	detail.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	add_child(HSeparator.new())
	hide()


static func current(context: Dictionary, snapshot: Dictionary, reviewing: bool) -> bool:
	var state = snapshot.get("summary", {})
	var view = snapshot.get("view")
	if reviewing or context.is_empty() or not view is Dictionary:
		return false
	# JSON seat numbers are floats; normalize before Array membership checks.
	var owned = snapshot.get("you", {}).get("seats", []).any(func(seat): return int(seat) == int(context.seat))
	return owned and int(view.get("player", -1)) == int(context.seat) and state.get("game_id") == context.game and int(state.get("undo_count", 0)) == int(context.undo) and int(state.get("revision", -1)) >= int(context.revision)


static func confirmed(context: Dictionary, snapshot: Dictionary, reviewing: bool) -> bool:
	return current(context, snapshot, reviewing) and int(snapshot.summary.revision) > int(context.revision)


func capture() -> Dictionary:
	reset()
	var model = table.model
	var players = model.view().get("players", [])
	var seat = model.active_seat
	var player = players[seat] if seat >= 0 and seat < players.size() else {}
	return {"game": table.game_id, "seat": seat, "revision": int(model.summary().get("revision", -1)), "undo": int(model.summary().get("undo_count", 0)), "resources": player.get("resources", {}).duplicate(), "vp": int(player.get("victory_points", 0))}


func reset() -> void:
	receipt.clear()
	if heading != null:
		heading.text = ""
	if detail != null:
		detail.text = ""
	set_meta("feedback_state", "none")
	hide()


func complete(context: Dictionary, action: Dictionary, reply: Dictionary) -> void:
	if not current(context, table.model.snapshot, not table.tools_ui.review.is_empty()):
		return
	receipt = {"context": context, "action": action.duplicate(true), "accepted": bool(reply.get("ok", false))}
	if not receipt.accepted:
		var data = reply.get("data")
		receipt.error = str(data.get("detail", "")) if data is Dictionary else ""
	refresh()


func refresh() -> void:
	if receipt.is_empty():
		hide()
		return
	var context: Dictionary = receipt.context
	if not current(context, table.model.snapshot, not table.tools_ui.review.is_empty()):
		reset()
		return
	var words = ""
	var color = Color("bce7d0")
	if not receipt.accepted:
		heading.text = table.model.native("처리하지 못했습니다")
		words = str(receipt.error)
		color = Color("f2ca89")
		set_meta("feedback_state", "rejected")
	elif not confirmed(context, table.model.snapshot, false):
		heading.text = table.model.native("서버 응답 수신 · 화면 확인 중")
		color = Color("a4dcec")
		set_meta("feedback_state", "unconfirmed")
	else:
		heading.text = table.model.native("✓ 실행됨 · ") + table.model.action_heading(receipt.action)
		# Freeze the observed net change once confirmed, so later AI/poll updates
		# cannot be attributed to this receipt. No hidden draw/deck is inspected.
		if not receipt.has("delta"):
			var player = table.model.view().players[int(context.seat)]
			var delta: Dictionary = {}
			for key in ["solari", "spice", "water"]:
				var value = int(player.get("resources", {}).get(key, 0)) - int(context.resources.get(key, 0))
				if value:
					delta[key] = value
			var vp = int(player.get("victory_points", 0)) - int(context.vp)
			if vp:
				delta.victory_point = vp
			receipt.delta = delta
		var changes: PackedStringArray = []
		for key in receipt.delta:
			changes.append(table.model.phrase("{" + key + "}") + " " + ("+" if int(receipt.delta[key]) > 0 else "") + str(int(receipt.delta[key])))
		words = " · ".join(changes)
		set_meta("feedback_state", "confirmed")
	heading.add_theme_color_override("font_color", color)
	detail.text = words
	detail.visible = not words.is_empty()
	tooltip_text = heading.text + ("\n" + words if not words.is_empty() else "")
	show()
