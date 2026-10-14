extends SceneTree

const DisplayScale = preload("res://display_scale.gd")
var checks = 0
var failed = false


func _initialize() -> void:
	call_deferred("run")


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failed = true
		push_error("GODOT_DISPLAY_SCALE_FAILED: " + message)


func settled() -> void:
	await process_frame
	await process_frame
	await process_frame


func run() -> void:
	for sample in [
		[Vector2i(1920, 1080), 96, 1.0, 1.0],
		[Vector2i(2560, 1440), 96, 1.0, 1.25],
		[Vector2i(3840, 2160), 96, 1.0, 2.0],
		[Vector2i(3840, 2160), 192, 1.0, 2.0],
		[Vector2i(3840, 2160), 192, 2.0, 2.0],
		[Vector2i(1920, 1080), 144, 1.0, 1.5],
		[Vector2i(2160, 3840), 96, 1.0, 2.0],
		[Vector2i(5120, 1440), 96, 1.0, 1.25],
		[Vector2i.ZERO, 0, 1.0, 1.0],
	]:
		check(is_equal_approx(DisplayScale.preferred_scale(sample[0], sample[1], sample[2]), sample[3]), "resolution/DPI/Retina scale: " + str(sample))
	check(DisplayScale.initial_size(2.0, Vector2i(3840, 2080)) == Vector2i(2880, 1800), "4K starts with a readable window at twice the original size")
	check(DisplayScale.initial_size(1.5, Vector2i(1920, 1040)) == Vector2i(1888, 992), "startup respects the usable desktop and title bar")
	root.size = Vector2i(2880, 1800)
	var scaling = DisplayScale.new()
	root.add_child(scaling)
	scaling.setup(root)
	scaling.set_process(false)
	scaling.monitor_scale = 2.0
	scaling._apply_scale()
	var surface = Control.new()
	root.add_child(surface)
	surface.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var button = Button.new()
	button.text = "Test"
	button.position = Vector2(60, 70)
	button.size = Vector2(160, 42)
	surface.add_child(button)
	var pressed = [false]
	button.pressed.connect(func(): pressed[0] = true)
	await settled()
	check(surface.size.is_equal_approx(Vector2(1440, 900)), "2x preserves the logical table and native layout area")
	check(root.get_final_transform().x.is_equal_approx(Vector2(2, 0)), "2x doubles physical font/button/card coordinates")
	var point = root.get_final_transform() * button.get_global_rect().get_center()
	for down in [true, false]:
		var event = InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = down
		event.position = point
		event.global_position = point
		Input.parse_input_event(event)
		await process_frame
	check(pressed[0], "physical clicks hit the scaled native control")
	var popup = AcceptDialog.new()
	root.add_child(popup)
	popup.popup_centered(Vector2i(600, 400))
	await settled()
	check(popup.is_embedded(), "information popup stays in the scaled table")
	check(Rect2(Vector2.ZERO, surface.size).encloses(Rect2(Vector2(popup.position), Vector2(popup.size))), "popup centers in logical coordinates rather than raw 4K pixels")
	popup.queue_free()
	for pixels in [Vector2i(3840, 2160), Vector2i(2880, 1800), Vector2i(1920, 1080), Vector2i(1440, 900), Vector2i(1100, 740)]:
		root.size = pixels
		await settled()
		check(root.content_scale_factor == DisplayScale.fitting_scale(2.0, pixels), "live resize caps the scale to the readable table: " + str(pixels))
		check(surface.size.x >= 1100 and surface.size.y >= 740, "resize retains the minimum table area: " + str(pixels))
	root.size = Vector2i(1440, 900)
	scaling.monitor_scale = 1.0
	scaling._apply_scale()
	await settled()
	check(root.content_scale_factor == 1.0 and surface.size == Vector2(1440, 900), "returning to an FHD monitor restores the original layout")
	surface.queue_free()
	scaling.queue_free()
	await settled()
	print("GODOT_DISPLAY_SCALE_OK %d" % checks)
	quit(1 if failed else 0)
