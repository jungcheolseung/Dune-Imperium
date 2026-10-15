extends BoxContainer

# One authorized catalog entry: artwork beside the same text used by hover.
# The image keeps its own aspect ratio; long text scrolls with the dialog.
var table: Control
var ref = ""
var picture: TextureRect
var heading: Label
var words: Label
var body: VBoxContainer
var compact = false


func setup(owner_table: Control, target: String, entry: Dictionary, small = false) -> void:
	table = owner_table
	ref = target
	compact = small
	set_meta("entry_view", true)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation", 18)
	picture = table._picture(self, table._image_path(entry), Vector2.ZERO)
	picture.ref = ref
	picture.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	body = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 12)
	add_child(body)
	# Configure wrapping before adding real text to a visible dialog; an
	# unwrapped ability can otherwise expand Window's minimum width first.
	heading = table._label(body, "", 20)
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.text = table.model.name_of(ref)
	words = table._label(body, "", 16)
	words.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	words.text = table._entry_words(entry, ref)
	resized.connect(_fit)
	table.api.texture_ready.connect(_texture_ready)
	_fit.call_deferred()


func _texture_ready(path: String, texture: Texture2D) -> void:
	if path == picture.get_meta("image_path", ""):
		picture.texture = texture
		_fit()


func _fit() -> void:
	if picture == null:
		return
	picture.visible = not str(picture.get_meta("image_path", "")).is_empty()
	var available = size.x if size.x > 0 else 680.0
	vertical = not compact and available < 520
	var ratio = 0.7
	if picture.texture != null:
		ratio = float(picture.texture.get_width()) / picture.texture.get_height()
	var maximum_height = 150.0 if compact else 350.0
	var width = minf(available * (0.28 if compact else 0.38), 130 if compact else 300 if ratio > 1.1 else 245)
	if vertical:
		width = minf(available, maximum_height * ratio)
	# Container allocation uses whole logical pixels. Keep the requested
	# minimum on that grid as well, including non-integer card aspect ratios.
	picture.custom_minimum_size = Vector2(floorf(width), floorf(minf(maximum_height, width / ratio)))
	picture.size_flags_horizontal = Control.SIZE_SHRINK_CENTER if vertical else Control.SIZE_FILL


func layout_fits() -> bool:
	var bounds = Rect2(Vector2.ZERO, size)
	var fits = bounds.encloses(body.get_rect()) and (not picture.visible or (bounds.encloses(picture.get_rect()) and not picture.get_rect().intersects(body.get_rect())))
	if not fits:
		print("GODOT_ENTRY_LAYOUT ", JSON.stringify({"bounds": str(bounds), "body": str(body.get_rect()), "picture": str(picture.get_rect()), "vertical": vertical}))
	return fits
