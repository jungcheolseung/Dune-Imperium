extends Node

# Keep UI coordinates responsive; Window scales fonts, cards and input together.
# https://docs.godotengine.org/en/4.6/tutorials/rendering/multiple_resolutions.html#stretch-scale
const BASE_WINDOW = Vector2i(1440, 900)
const MIN_WINDOW = Vector2i(1100, 740)
const REFERENCE_SCREEN = Vector2(1920, 1080)

var window: Window
var monitor_scale = 1.0
var monitor_signature = ""
var elapsed = 0.0


static func preferred_scale(screen_size: Vector2i, dpi = 96, native_scale = 1.0) -> float:
	var landscape = Vector2(maxi(screen_size.x, screen_size.y), mini(screen_size.x, screen_size.y))
	var resolution = minf(landscape.x / REFERENCE_SCREEN.x, landscape.y / REFERENCE_SCREEN.y)
	# Use the larger hint, not a product that doubles Windows/Retina scaling.
	var desired = maxf(resolution, maxf(float(dpi) / 96.0, native_scale))
	return clampf(roundf(desired * 4.0) / 4.0, 1.0, 4.0)


static func fitting_scale(desired: float, pixels: Vector2i) -> float:
	var capacity = minf(float(pixels.x) / MIN_WINDOW.x, float(pixels.y) / MIN_WINDOW.y)
	var fitted = minf(desired, floorf(capacity * 4.0) / 4.0)
	return maxf(0.75, fitted)


static func initial_size(desired: float, usable: Vector2i) -> Vector2i:
	return Vector2i(Vector2(BASE_WINDOW) * desired).min(usable - Vector2i(32, 48))


func setup(owner_window: Window) -> void:
	window = owner_window
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	_refresh_monitor(true)
	window.size_changed.connect(_apply_scale)
	_apply_scale()


func _process(delta: float) -> void:
	elapsed += delta
	if elapsed >= 0.5:
		elapsed = 0.0
		_refresh_monitor()


func _refresh_monitor(startup = false) -> void:
	if window == null:
		return
	if DisplayServer.get_name() == "headless":
		window.min_size = MIN_WINDOW
		return
	var screen = window.current_screen
	var pixels = DisplayServer.screen_get_size(screen)
	var dpi = DisplayServer.screen_get_dpi(screen)
	var native_scale = DisplayServer.screen_get_scale(DisplayServer.SCREEN_OF_MAIN_WINDOW)
	var usable = DisplayServer.screen_get_usable_rect(screen)
	var signature = str([screen, pixels, dpi, native_scale, usable])
	if signature == monitor_signature or pixels.x <= 0 or pixels.y <= 0:
		return
	var logical = Vector2(window.size) / window.content_scale_factor
	monitor_signature = signature
	monitor_scale = preferred_scale(pixels, dpi, native_scale)
	window.min_size = MIN_WINDOW.min(usable.size - Vector2i(32, 48))
	var explicit_size = "--resolution" in OS.get_cmdline_args()
	if window.mode == Window.MODE_WINDOWED and (not startup or not explicit_size):
		window.size = initial_size(monitor_scale, usable.size) if startup else Vector2i(logical * monitor_scale).min(usable.size - Vector2i(32, 48))
		if startup:
			window.move_to_center()
		else:
			window.position = window.position.clamp(usable.position, usable.end - window.size - Vector2i(0, 32))
	_apply_scale()


func _apply_scale() -> void:
	var desired = fitting_scale(monitor_scale, window.size)
	if not is_equal_approx(window.content_scale_factor, desired):
		window.content_scale_factor = desired
